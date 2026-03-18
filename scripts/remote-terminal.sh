#!/bin/bash
# ============================================================
# Remote Terminal — Acesso seguro ao terminal via browser
# Usa: ttyd + caddy (basic auth) + ngrok (tunnel) + qrencode
# ============================================================
# Adicione ao seu .bashrc/.zshrc:
#   source /caminho/para/remote-terminal.sh
# ============================================================

REMOTE_TERM_PORT_TTYD=7681
REMOTE_TERM_PORT_CADDY=7682
REMOTE_TERM_PID_DIR="/tmp"

remote-terminal() {
    echo "🖥️  Iniciando Remote Terminal..."
    echo ""

    # ---- Verificar dependências ----
    local missing=()
    for cmd in ttyd ngrok caddy qrencode; do
        command -v "$cmd" &>/dev/null || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "❌ Dependências faltando: ${missing[*]}"
        echo ""
        echo "Instale com:"
        echo "  Ubuntu/Debian: sudo apt install ttyd qrencode caddy && snap install ngrok"
        echo "  macOS:         brew install ttyd ngrok caddy qrencode"
        echo "  Arch:          yay -S ttyd ngrok caddy qrencode"
        echo ""
        echo "Ou manualmente:"
        echo "  ttyd:     https://github.com/tsl0922/ttyd/releases"
        echo "  ngrok:    https://ngrok.com/download (precisa de conta gratuita + authtoken)"
        echo "  caddy:    https://caddyserver.com/download"
        echo "  qrencode: https://github.com/fukuchi/libqrencode"
        return 1
    fi

    # ---- Verificar se já está rodando ----
    if [[ -f "$REMOTE_TERM_PID_DIR/ttyd.pid" ]]; then
        local old_pid
        old_pid=$(cat "$REMOTE_TERM_PID_DIR/ttyd.pid" 2>/dev/null)
        if kill -0 "$old_pid" 2>/dev/null; then
            echo "⚠️  Remote terminal já está rodando (ttyd PID $old_pid)"
            echo "   Use 'stop-remote-terminal' primeiro."
            return 1
        fi
    fi

    # ---- Gerar credenciais ----
    local RT_USER="admin"
    local RT_PASS
    RT_PASS=$(openssl rand -hex 4)
    local RT_PASS_HASH
    RT_PASS_HASH=$(caddy hash-password --plaintext "$RT_PASS" 2>/dev/null)

    if [[ -z "$RT_PASS_HASH" ]]; then
        echo "❌ Falha ao gerar hash da senha com caddy"
        return 1
    fi

    # ---- Iniciar ttyd (terminal web na porta 7681) ----
    echo "1/4  Iniciando ttyd na porta $REMOTE_TERM_PORT_TTYD..."
    if command -v tmux &>/dev/null; then
        # Criar sessão tmux dedicada
        tmux new-session -d -s remote-term 2>/dev/null || true
        ttyd --port "$REMOTE_TERM_PORT_TTYD" --writable tmux attach -t remote-term &
    else
        ttyd --port "$REMOTE_TERM_PORT_TTYD" --writable bash &
    fi
    echo $! > "$REMOTE_TERM_PID_DIR/ttyd.pid"
    sleep 1

    if ! kill -0 "$(cat "$REMOTE_TERM_PID_DIR/ttyd.pid")" 2>/dev/null; then
        echo "❌ ttyd falhou ao iniciar"
        return 1
    fi

    # ---- Criar Caddyfile com basic auth (porta 7682 → 7681) ----
    echo "2/4  Configurando Caddy (basic auth) na porta $REMOTE_TERM_PORT_CADDY..."
    local CADDYFILE="$REMOTE_TERM_PID_DIR/Caddyfile.remote-term"
    cat > "$CADDYFILE" <<CADDYEOF
:${REMOTE_TERM_PORT_CADDY} {
    basicauth /* {
        ${RT_USER} ${RT_PASS_HASH}
    }
    reverse_proxy localhost:${REMOTE_TERM_PORT_TTYD}
}
CADDYEOF

    caddy start --config "$CADDYFILE" --adapter caddyfile &>/dev/null
    echo $! > "$REMOTE_TERM_PID_DIR/caddy.pid"
    sleep 1

    # ---- Iniciar ngrok tunnel ----
    echo "3/4  Abrindo tunnel ngrok..."
    ngrok http "$REMOTE_TERM_PORT_CADDY" --log=stdout --log-level=warn &>/dev/null &
    echo $! > "$REMOTE_TERM_PID_DIR/ngrok.pid"

    # ---- Aguardar URL pública do ngrok ----
    echo "4/4  Aguardando URL pública..."
    local PUBLIC_URL=""
    local attempts=0
    while [[ -z "$PUBLIC_URL" ]] && [[ $attempts -lt 15 ]]; do
        sleep 1
        PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
            | python3 -c "import sys,json; t=json.load(sys.stdin)['tunnels']; print(t[0]['public_url'] if t else '')" 2>/dev/null)
        ((attempts++))
    done

    if [[ -z "$PUBLIC_URL" ]]; then
        echo "❌ ngrok não retornou URL pública"
        echo "   Verifique se o ngrok authtoken está configurado: ngrok config add-authtoken <TOKEN>"
        stop-remote-terminal
        return 1
    fi

    # ---- Exibir resultado ----
    echo ""
    echo "============================================================"
    echo "  🖥️  REMOTE TERMINAL ATIVO"
    echo "============================================================"
    echo ""
    echo "  URL:    $PUBLIC_URL"
    echo "  User:   $RT_USER"
    echo "  Senha:  $RT_PASS"
    echo ""
    echo "============================================================"
    echo ""

    # ---- QR Code ----
    # Formato com credenciais embutidas: https://user:pass@host
    local QR_URL
    QR_URL=$(echo "$PUBLIC_URL" | sed "s|https://|https://${RT_USER}:${RT_PASS}@|")

    if command -v qrencode &>/dev/null; then
        echo "  📱 Escaneie o QR code para acessar:"
        echo ""
        qrencode -t UTF8 "$QR_URL"
        echo ""
    fi

    echo "  Para parar: stop-remote-terminal"
    echo "============================================================"

    # ---- Salvar info ----
    cat > "$REMOTE_TERM_PID_DIR/remote-term-info.txt" <<EOF
URL=$PUBLIC_URL
USER=$RT_USER
PASS=$RT_PASS
QR_URL=$QR_URL
STARTED=$(date -Iseconds)
EOF
}

stop-remote-terminal() {
    echo "🛑 Parando Remote Terminal..."

    local stopped=0

    # Matar por PID files
    for svc in ngrok caddy ttyd; do
        local pidfile="$REMOTE_TERM_PID_DIR/${svc}.pid"
        if [[ -f "$pidfile" ]]; then
            local pid
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null
                echo "  ✓ $svc (PID $pid) parado"
                ((stopped++))
            fi
            rm -f "$pidfile"
        fi
    done

    # Caddy stop graceful
    caddy stop &>/dev/null 2>&1

    # Fallback: pkill
    for proc in ttyd caddy ngrok; do
        if pkill -f "$proc" 2>/dev/null; then
            echo "  ✓ $proc (pkill fallback)"
            ((stopped++))
        fi
    done

    # Limpar tmux session
    tmux kill-session -t remote-term 2>/dev/null

    # Limpar arquivos
    rm -f "$REMOTE_TERM_PID_DIR/Caddyfile.remote-term"
    rm -f "$REMOTE_TERM_PID_DIR/remote-term-info.txt"

    if [[ $stopped -eq 0 ]]; then
        echo "  ℹ️  Nenhum processo encontrado (já estava parado)"
    else
        echo ""
        echo "  ✅ Remote Terminal desligado"
    fi
}

# Atalho
alias rt='remote-terminal'
alias srt='stop-remote-terminal'
