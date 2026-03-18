#!/usr/bin/env bash
# ============================================================================
# worker-health-check.sh — Health check completo dos workers LXC com Claude Code
#
# Uso:
#   ./worker-health-check.sh [--json] [--watch]
#
# Verifica: estado, RAM, disco, Claude instalado, OAuth token valido
# ============================================================================

set -euo pipefail

# --- Cores ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

CLAUDE_USER="claude"

# Workers
SAAS_WORKERS=()
for i in $(seq -w 1 13); do
    SAAS_WORKERS+=("worker-$i")
done
DUXFIT_WORKERS=("duxfit-worker-01" "duxfit-worker-02")
ALL_WORKERS=("${SAAS_WORKERS[@]}" "${DUXFIT_WORKERS[@]}")

# --- Contadores globais ---
TOTAL=0
RUNNING=0
STOPPED=0
HEALTHY=0
DEGRADED=0
CRITICAL=0

# --- Helpers ---

lxc_exec_as_claude() {
    local worker="$1"; shift
    lxc exec "$worker" -- su - "$CLAUDE_USER" -c "$*" 2>/dev/null
}

lxc_exec_root() {
    local worker="$1"; shift
    lxc exec "$worker" -- "$@" 2>/dev/null
}

get_worker_state() {
    lxc info "$1" 2>/dev/null | grep -i "^Status:" | awk '{print $2}' || echo "UNKNOWN"
}

# Colorir porcentagem de uso (verde < 60%, amarelo < 85%, vermelho >= 85%)
color_pct() {
    local val="$1"
    local num="${val%\%}"
    num="${num%%.*}"
    if [[ "$num" -lt 60 ]]; then
        echo -e "${GREEN}${val}${NC}"
    elif [[ "$num" -lt 85 ]]; then
        echo -e "${YELLOW}${val}${NC}"
    else
        echo -e "${RED}${val}${NC}"
    fi
}

# --- Coletar dados de um worker ---

check_single_worker() {
    local worker="$1"
    local state
    state=$(get_worker_state "$worker")

    ((TOTAL++))

    if [[ "$state" != "RUNNING" ]]; then
        ((STOPPED++))
        printf "  ${RED}%-22s${NC} %-10s ${DIM}%-8s %-8s %-14s %-10s %-10s${NC}\n" \
            "$worker" "$state" "—" "—" "—" "—" "—"
        return
    fi

    ((RUNNING++))

    # --- RAM ---
    local ram_info
    ram_info=$(lxc_exec_root "$worker" sh -c \
        "free -m 2>/dev/null | awk '/^Mem:/ {printf \"%dM/%dM %d%%\", \$3, \$2, (\$3/\$2)*100}'" \
        || echo "?")
    ram_info=$(echo "$ram_info" | tr -d '\r')

    local ram_pct
    ram_pct=$(echo "$ram_info" | grep -oP '\d+%' || echo "0%")

    # --- Disco ---
    local disk_info
    disk_info=$(lxc_exec_root "$worker" sh -c \
        "df -h / 2>/dev/null | awk 'NR==2 {printf \"%s/%s %s\", \$3, \$2, \$5}'" \
        || echo "?")
    disk_info=$(echo "$disk_info" | tr -d '\r')

    local disk_pct
    disk_pct=$(echo "$disk_info" | grep -oP '\d+%' || echo "0%")

    # --- Claude Code ---
    local claude_ver
    claude_ver=$(lxc_exec_as_claude "$worker" "claude --version 2>/dev/null" || echo "")
    claude_ver=$(echo "$claude_ver" | head -1 | tr -d '\r')

    local claude_status
    if [[ -n "$claude_ver" && "$claude_ver" != "N/A" ]]; then
        claude_status="${GREEN}$claude_ver${NC}"
    else
        claude_status="${RED}NAO INSTALADO${NC}"
    fi

    # --- OAuth Token ---
    local oauth_status
    local token_check
    token_check=$(lxc_exec_as_claude "$worker" \
        "test -f ~/.claude/.credentials.json && echo 'EXISTS' || echo 'MISSING'" || echo "MISSING")
    token_check=$(echo "$token_check" | tr -d '\r')

    if [[ "$token_check" == "EXISTS" ]]; then
        # Verificar se nao esta expirado (checando se o arquivo tem conteudo valido)
        local token_valid
        token_valid=$(lxc_exec_as_claude "$worker" \
            "python3 -c \"
import json, sys
try:
    d = json.load(open('/home/claude/.claude/.credentials.json'))
    if d.get('oauthAccount') or d.get('claudeAiOauth'):
        print('VALID')
    else:
        print('EMPTY')
except:
    print('INVALID')
\" 2>/dev/null" || echo "?")
        token_valid=$(echo "$token_valid" | tr -d '\r')

        case "$token_valid" in
            VALID)   oauth_status="${GREEN}VALIDO${NC}" ;;
            EMPTY)   oauth_status="${YELLOW}VAZIO${NC}" ;;
            INVALID) oauth_status="${RED}INVALIDO${NC}" ;;
            *)       oauth_status="${YELLOW}?${NC}" ;;
        esac
    else
        oauth_status="${RED}AUSENTE${NC}"
    fi

    # --- Uptime ---
    local uptime_str
    uptime_str=$(lxc_exec_root "$worker" sh -c "uptime -p 2>/dev/null || uptime" || echo "?")
    uptime_str=$(echo "$uptime_str" | tr -d '\r' | sed 's/^up //')

    # --- Health score ---
    local health="HEALTHY"
    local ram_num="${ram_pct%\%}"
    local disk_num="${disk_pct%\%}"

    if [[ -z "$claude_ver" || "$claude_ver" == "N/A" ]]; then
        health="CRITICAL"
    elif [[ "$token_check" != "EXISTS" ]]; then
        health="DEGRADED"
    elif [[ "$ram_num" -ge 90 || "$disk_num" -ge 90 ]]; then
        health="CRITICAL"
    elif [[ "$ram_num" -ge 75 || "$disk_num" -ge 80 ]]; then
        health="DEGRADED"
    fi

    case "$health" in
        HEALTHY)  ((HEALTHY++));  local health_color="${GREEN}OK${NC}" ;;
        DEGRADED) ((DEGRADED++)); local health_color="${YELLOW}WARN${NC}" ;;
        CRITICAL) ((CRITICAL++)); local health_color="${RED}CRIT${NC}" ;;
    esac

    # --- Imprimir linha ---
    printf "  %-22s ${GREEN}%-10s${NC} %-20b %-20b %-22b %-18b %-8b\n" \
        "$worker" \
        "$state" \
        "$(color_pct "$ram_pct") ${DIM}($ram_info)${NC}" \
        "$(color_pct "$disk_pct") ${DIM}($disk_info)${NC}" \
        "$claude_status" \
        "$oauth_status" \
        "$health_color"
}

# --- Tabela principal ---

run_health_check() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo ""
    echo -e "${BOLD}${CYAN}=====================================================================${NC}"
    echo -e "${BOLD}${CYAN}  WORKER HEALTH CHECK — Claude Code LXC Fleet${NC}"
    echo -e "${BOLD}${CYAN}  $timestamp${NC}"
    echo -e "${BOLD}${CYAN}=====================================================================${NC}"
    echo ""

    # Header
    printf "  ${BOLD}%-22s %-10s %-20s %-20s %-22s %-18s %-8s${NC}\n" \
        "WORKER" "ESTADO" "RAM" "DISCO" "CLAUDE CODE" "OAUTH" "SAUDE"
    printf "  %-22s %-10s %-20s %-20s %-22s %-18s %-8s\n" \
        "$(printf '%0.s-' {1..22})" \
        "$(printf '%0.s-' {1..10})" \
        "$(printf '%0.s-' {1..20})" \
        "$(printf '%0.s-' {1..20})" \
        "$(printf '%0.s-' {1..22})" \
        "$(printf '%0.s-' {1..18})" \
        "$(printf '%0.s-' {1..8})"

    # VPS SaaS
    echo ""
    echo -e "  ${MAGENTA}${BOLD}VPS SaaS (95.111.241.168)${NC}"
    for worker in "${SAAS_WORKERS[@]}"; do
        check_single_worker "$worker"
    done

    # VPS DuxFit
    echo ""
    echo -e "  ${MAGENTA}${BOLD}VPS DuxFit (213.136.93.112)${NC}"
    for worker in "${DUXFIT_WORKERS[@]}"; do
        check_single_worker "$worker"
    done

    # --- Resumo ---
    echo ""
    echo -e "${BOLD}${CYAN}---------------------------------------------------------------------${NC}"
    echo -e "  ${BOLD}RESUMO:${NC}"
    echo -e "    Total:    ${BOLD}$TOTAL${NC} workers"
    echo -e "    Running:  ${GREEN}$RUNNING${NC}"
    echo -e "    Stopped:  ${RED}$STOPPED${NC}"
    echo -e "    Healthy:  ${GREEN}$HEALTHY${NC}"
    echo -e "    Degraded: ${YELLOW}$DEGRADED${NC}"
    echo -e "    Critical: ${RED}$CRITICAL${NC}"
    echo -e "${BOLD}${CYAN}---------------------------------------------------------------------${NC}"
    echo ""

    # Alertas
    if [[ $CRITICAL -gt 0 ]]; then
        echo -e "  ${RED}${BOLD}!! $CRITICAL worker(s) em estado CRITICO — acao necessaria !!${NC}"
        echo ""
    fi
    if [[ $DEGRADED -gt 0 ]]; then
        echo -e "  ${YELLOW}${BOLD}** $DEGRADED worker(s) degradado(s) — verificar **${NC}"
        echo ""
    fi
    if [[ $STOPPED -gt 0 ]]; then
        echo -e "  ${DIM}$STOPPED worker(s) parado(s). Inicie com: lxc start <worker>${NC}"
        echo ""
    fi
}

# --- JSON output ---

run_health_check_json() {
    echo "{"
    echo '  "timestamp": "'$(date -u '+%Y-%m-%dT%H:%M:%SZ')'",'
    echo '  "workers": ['

    local first=true
    for worker in "${ALL_WORKERS[@]}"; do
        local state
        state=$(get_worker_state "$worker")

        if [[ "$first" == true ]]; then
            first=false
        else
            echo ","
        fi

        if [[ "$state" != "RUNNING" ]]; then
            printf '    {"name": "%s", "state": "%s", "healthy": false}' "$worker" "$state"
            continue
        fi

        local ram_mb
        ram_mb=$(lxc_exec_root "$worker" sh -c \
            "free -m 2>/dev/null | awk '/^Mem:/ {printf \"{\\\"used\\\": %d, \\\"total\\\": %d}\", \$3, \$2}'" \
            || echo '{"used": 0, "total": 0}')

        local disk_pct
        disk_pct=$(lxc_exec_root "$worker" sh -c \
            "df / 2>/dev/null | awk 'NR==2 {gsub(/%/,\"\",\$5); print \$5}'" || echo "0")
        disk_pct=$(echo "$disk_pct" | tr -d '\r')

        local claude_ver
        claude_ver=$(lxc_exec_as_claude "$worker" "claude --version 2>/dev/null" || echo "")
        claude_ver=$(echo "$claude_ver" | head -1 | tr -d '\r')

        local has_oauth
        has_oauth=$(lxc_exec_as_claude "$worker" \
            "test -f ~/.claude/.credentials.json && echo true || echo false" || echo "false")
        has_oauth=$(echo "$has_oauth" | tr -d '\r')

        printf '    {"name": "%s", "state": "%s", "ram": %s, "disk_pct": %s, "claude_version": "%s", "oauth": %s, "healthy": true}' \
            "$worker" "$state" "$ram_mb" "$disk_pct" "$claude_ver" "$has_oauth"
    done

    echo ""
    echo "  ]"
    echo "}"
}

# --- Watch mode (atualiza a cada 30s) ---

run_watch() {
    while true; do
        clear
        TOTAL=0; RUNNING=0; STOPPED=0; HEALTHY=0; DEGRADED=0; CRITICAL=0
        run_health_check
        echo -e "${DIM}  Atualizando a cada 30s... Ctrl+C para sair${NC}"
        sleep 30
    done
}

# --- Main ---

show_usage() {
    echo ""
    echo -e "${BOLD}worker-health-check.sh${NC} — Health check dos workers LXC"
    echo ""
    echo "Uso:"
    echo "  $0              Executa health check completo (tabela colorida)"
    echo "  $0 --json       Output em JSON (para integracao)"
    echo "  $0 --watch      Modo watch (atualiza a cada 30s)"
    echo ""
}

case "${1:-}" in
    --json)
        run_health_check_json
        ;;
    --watch)
        run_watch
        ;;
    --help|-h)
        show_usage
        ;;
    "")
        run_health_check
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
