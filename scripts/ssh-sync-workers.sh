#!/usr/bin/env bash
# ============================================================================
# ssh-sync-workers.sh — Sincroniza Claude Code config e projetos entre workers LXC
#
# Uso:
#   ./ssh-sync-workers.sh [sync-config|sync-projects|sync-all|status|setup-keys]
#
# Workers:
#   VPS SaaS (95.111.241.168): worker-01 a worker-13
#   VPS DuxFit (213.136.93.112): duxfit-worker-01, duxfit-worker-02
# ============================================================================

set -euo pipefail

# --- Cores ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# --- Config ---
SSH_KEY="$HOME/.ssh/claude_sync"
CLAUDE_USER="claude"
TMP_DIR="/tmp/claude-sync"
CONFIG_ARCHIVE="/tmp/claude-config.tar.gz"

# Workers SaaS (VPS 95.111.241.168)
SAAS_WORKERS=()
for i in $(seq -w 1 13); do
    SAAS_WORKERS+=("worker-$i")
done

# Workers DuxFit (VPS 213.136.93.112)
DUXFIT_WORKERS=("duxfit-worker-01" "duxfit-worker-02")

# Todos os workers
ALL_WORKERS=("${SAAS_WORKERS[@]}" "${DUXFIT_WORKERS[@]}")

# Projetos para sync
declare -A PROJECT_PATHS
PROJECT_PATHS["crm-saas-kanban"]="/opt/crm-saas-kanban"
PROJECT_PATHS["agent-hub"]="/opt/agent-hub"

# Quais projetos vao para quais workers
# crm-saas-kanban -> apenas SaaS workers
# agent-hub -> todos

# --- Funcoes utilitarias ---

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_err()   { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "\n${BOLD}${CYAN}==> $*${NC}"; }

worker_is_saas() {
    local w="$1"
    [[ "$w" == worker-* ]]
}

worker_is_duxfit() {
    local w="$1"
    [[ "$w" == duxfit-worker-* ]]
}

lxc_exec() {
    local worker="$1"
    shift
    lxc exec "$worker" -- "$@"
}

lxc_exec_as_claude() {
    local worker="$1"
    shift
    lxc exec "$worker" -- su - "$CLAUDE_USER" -c "$*"
}

check_worker_online() {
    local worker="$1"
    lxc info "$worker" &>/dev/null 2>&1
    return $?
}

get_worker_state() {
    local worker="$1"
    lxc info "$worker" 2>/dev/null | grep -i "^Status:" | awk '{print $2}' || echo "UNKNOWN"
}

# --- PASSO 1: Gerar chave SSH na master ---

setup_ssh_keys() {
    log_step "PASSO 1 — Gerando chave SSH na master"

    if [[ -f "$SSH_KEY" ]]; then
        log_warn "Chave SSH ja existe em $SSH_KEY"
        read -rp "Deseja regenerar? (s/N): " resp
        if [[ "$resp" != "s" && "$resp" != "S" ]]; then
            log_info "Mantendo chave existente."
        else
            rm -f "$SSH_KEY" "$SSH_KEY.pub"
            ssh-keygen -t rsa -b 4096 -f "$SSH_KEY" -N "" -C "claude-sync-master@$(hostname)"
            log_ok "Nova chave gerada: $SSH_KEY"
        fi
    else
        mkdir -p "$(dirname "$SSH_KEY")"
        ssh-keygen -t rsa -b 4096 -f "$SSH_KEY" -N "" -C "claude-sync-master@$(hostname)"
        log_ok "Chave gerada: $SSH_KEY"
    fi

    # --- PASSO 2: Autorizar nas slaves ---
    log_step "PASSO 2 — Autorizando chave publica nos workers"

    local pubkey
    pubkey=$(cat "$SSH_KEY.pub")
    local success=0
    local fail=0

    for worker in "${ALL_WORKERS[@]}"; do
        echo -n "  [$worker] "

        state=$(get_worker_state "$worker")
        if [[ "$state" != "RUNNING" ]]; then
            echo -e "${YELLOW}SKIP (estado: $state)${NC}"
            ((fail++))
            continue
        fi

        # Criar .ssh e definir permissoes
        lxc_exec_as_claude "$worker" "mkdir -p ~/.ssh && chmod 700 ~/.ssh" 2>/dev/null || true

        # Verificar se a chave ja esta autorizada
        local existing
        existing=$(lxc_exec_as_claude "$worker" "cat ~/.ssh/authorized_keys 2>/dev/null" || true)

        if echo "$existing" | grep -qF "$pubkey"; then
            echo -e "${GREEN}OK (ja autorizada)${NC}"
            ((success++))
            continue
        fi

        # Adicionar chave
        lxc_exec_as_claude "$worker" "echo '$pubkey' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys" 2>/dev/null

        if [[ $? -eq 0 ]]; then
            echo -e "${GREEN}OK${NC}"
            ((success++))
        else
            echo -e "${RED}FALHOU${NC}"
            ((fail++))
        fi
    done

    echo ""
    log_info "Resultado: ${GREEN}$success OK${NC} / ${RED}$fail falhas${NC}"
}

# --- PASSO 3: Sync ~/.claude/ da master para workers ---

sync_config() {
    log_step "PASSO 3 — Sincronizando ~/.claude/ para todos os workers"

    # Verificar se ~/.claude/ existe
    if [[ ! -d "$HOME/.claude" ]]; then
        log_err "Diretorio ~/.claude/ nao encontrado na master!"
        return 1
    fi

    # Compactar
    log_info "Compactando ~/.claude/ ..."
    mkdir -p "$TMP_DIR"
    tar -czf "$CONFIG_ARCHIVE" \
        -C "$HOME" \
        --exclude='.claude/scheduled-tasks/*/runs' \
        --exclude='.claude/projects/*/runs' \
        --exclude='.claude/statsig' \
        --exclude='.claude/todos' \
        .claude/

    local size
    size=$(du -sh "$CONFIG_ARCHIVE" | awk '{print $1}')
    log_info "Arquivo: $CONFIG_ARCHIVE ($size)"

    local success=0
    local fail=0

    for worker in "${ALL_WORKERS[@]}"; do
        echo -n "  [$worker] "

        state=$(get_worker_state "$worker")
        if [[ "$state" != "RUNNING" ]]; then
            echo -e "${YELLOW}SKIP (estado: $state)${NC}"
            ((fail++))
            continue
        fi

        # Push do arquivo
        lxc file push "$CONFIG_ARCHIVE" "$worker/home/$CLAUDE_USER/claude-config.tar.gz" 2>/dev/null
        if [[ $? -ne 0 ]]; then
            echo -e "${RED}FALHOU (push)${NC}"
            ((fail++))
            continue
        fi

        # Extrair no worker
        lxc_exec_as_claude "$worker" \
            "cd ~ && tar -xzf claude-config.tar.gz && rm -f claude-config.tar.gz" 2>/dev/null

        if [[ $? -eq 0 ]]; then
            echo -e "${GREEN}OK${NC}"
            ((success++))
        else
            echo -e "${RED}FALHOU (extract)${NC}"
            ((fail++))
        fi
    done

    # Cleanup
    rm -f "$CONFIG_ARCHIVE"

    echo ""
    log_info "Config sync: ${GREEN}$success OK${NC} / ${RED}$fail falhas${NC}"
}

# --- PASSO 4: Sync de projetos especificos ---

sync_projects() {
    log_step "PASSO 4 — Sincronizando projetos para os workers"

    mkdir -p "$TMP_DIR"

    # --- crm-saas-kanban (apenas SaaS workers) ---
    local crm_src="/opt/crm-saas-kanban"
    if [[ -d "$crm_src" ]]; then
        log_info "Compactando crm-saas-kanban..."
        tar -czf "$TMP_DIR/crm-saas-kanban.tar.gz" \
            -C "$(dirname "$crm_src")" \
            --exclude='node_modules' \
            --exclude='__pycache__' \
            --exclude='.git' \
            --exclude='*.pyc' \
            --exclude='.env' \
            "$(basename "$crm_src")"

        local size
        size=$(du -sh "$TMP_DIR/crm-saas-kanban.tar.gz" | awk '{print $1}')
        log_info "crm-saas-kanban: $size"

        for worker in "${SAAS_WORKERS[@]}"; do
            echo -n "  [$worker] crm-saas-kanban: "

            state=$(get_worker_state "$worker")
            if [[ "$state" != "RUNNING" ]]; then
                echo -e "${YELLOW}SKIP${NC}"
                continue
            fi

            lxc file push "$TMP_DIR/crm-saas-kanban.tar.gz" \
                "$worker/home/$CLAUDE_USER/crm-saas-kanban.tar.gz" 2>/dev/null

            lxc_exec_as_claude "$worker" \
                "cd ~ && tar -xzf crm-saas-kanban.tar.gz -C /opt/ && rm -f crm-saas-kanban.tar.gz" 2>/dev/null

            if [[ $? -eq 0 ]]; then
                echo -e "${GREEN}OK${NC}"
            else
                echo -e "${RED}FALHOU${NC}"
            fi
        done
    else
        log_warn "crm-saas-kanban nao encontrado em $crm_src — pulando"
    fi

    # --- agent-hub (todos os workers) ---
    local hub_src="/opt/agent-hub"
    if [[ -d "$hub_src" ]]; then
        log_info "Compactando agent-hub..."
        tar -czf "$TMP_DIR/agent-hub.tar.gz" \
            -C "$(dirname "$hub_src")" \
            --exclude='node_modules' \
            --exclude='__pycache__' \
            --exclude='.git' \
            --exclude='*.pyc' \
            --exclude='.env' \
            "$(basename "$hub_src")"

        local size
        size=$(du -sh "$TMP_DIR/agent-hub.tar.gz" | awk '{print $1}')
        log_info "agent-hub: $size"

        for worker in "${ALL_WORKERS[@]}"; do
            echo -n "  [$worker] agent-hub: "

            state=$(get_worker_state "$worker")
            if [[ "$state" != "RUNNING" ]]; then
                echo -e "${YELLOW}SKIP${NC}"
                continue
            fi

            lxc file push "$TMP_DIR/agent-hub.tar.gz" \
                "$worker/home/$CLAUDE_USER/agent-hub.tar.gz" 2>/dev/null

            lxc_exec_as_claude "$worker" \
                "cd ~ && tar -xzf agent-hub.tar.gz -C /opt/ && rm -f agent-hub.tar.gz" 2>/dev/null

            if [[ $? -eq 0 ]]; then
                echo -e "${GREEN}OK${NC}"
            else
                echo -e "${RED}FALHOU${NC}"
            fi
        done
    else
        log_warn "agent-hub nao encontrado em $hub_src — pulando"
    fi

    # Cleanup
    rm -rf "$TMP_DIR"

    echo ""
    log_ok "Sync de projetos concluido."
}

# --- Status check ---

check_status() {
    log_step "Status dos Workers LXC"

    printf "\n"
    printf "${BOLD}%-22s %-10s %-18s %-12s${NC}\n" "WORKER" "ESTADO" "CLAUDE VERSION" "CONFIG"
    printf "%-22s %-10s %-18s %-12s\n" "----------------------" "----------" "------------------" "------------"

    for worker in "${ALL_WORKERS[@]}"; do
        local state
        state=$(get_worker_state "$worker")

        local state_color
        if [[ "$state" == "RUNNING" ]]; then
            state_color="${GREEN}$state${NC}"
        elif [[ "$state" == "STOPPED" ]]; then
            state_color="${RED}$state${NC}"
        else
            state_color="${YELLOW}$state${NC}"
        fi

        local claude_ver="—"
        local config_status="—"

        if [[ "$state" == "RUNNING" ]]; then
            # Versao do Claude Code
            claude_ver=$(lxc_exec_as_claude "$worker" "claude --version 2>/dev/null || echo 'N/A'" 2>/dev/null || echo "N/A")
            claude_ver=$(echo "$claude_ver" | head -1 | tr -d '\r')

            # Verificar se ~/.claude/ existe
            local has_config
            has_config=$(lxc_exec_as_claude "$worker" "test -d ~/.claude && echo 'SIM' || echo 'NAO'" 2>/dev/null || echo "?")
            has_config=$(echo "$has_config" | tr -d '\r')

            if [[ "$has_config" == "SIM" ]]; then
                config_status="${GREEN}SIM${NC}"
            else
                config_status="${RED}NAO${NC}"
            fi
        fi

        printf "%-22s %-10b %-18s %-12b\n" "$worker" "$state_color" "$claude_ver" "$config_status"
    done

    echo ""
}

# --- Sync all ---

sync_all() {
    sync_config
    sync_projects
    check_status
}

# --- Main ---

show_usage() {
    echo ""
    echo -e "${BOLD}ssh-sync-workers.sh${NC} — Sincroniza Claude Code entre workers LXC"
    echo ""
    echo "Uso:"
    echo "  $0 setup-keys      Gera chave SSH e autoriza em todos os workers"
    echo "  $0 sync-config     Sincroniza ~/.claude/ para todos os workers"
    echo "  $0 sync-projects   Sincroniza projetos (crm-saas, agent-hub) para workers"
    echo "  $0 sync-all        Executa sync-config + sync-projects + status"
    echo "  $0 status          Verifica estado de cada worker"
    echo ""
    echo "Workers:"
    echo "  VPS SaaS:   worker-01 a worker-13"
    echo "  VPS DuxFit: duxfit-worker-01, duxfit-worker-02"
    echo ""
}

case "${1:-}" in
    setup-keys)
        setup_ssh_keys
        ;;
    sync-config)
        sync_config
        ;;
    sync-projects)
        sync_projects
        ;;
    sync-all)
        sync_all
        ;;
    status)
        check_status
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
