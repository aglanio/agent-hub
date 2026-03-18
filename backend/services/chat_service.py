"""Servico de chat — logica Anthropic + historico SQLite."""

import json
import os
from backend.config import ANTHROPIC_API_KEY
from backend.database import get_db
from backend.services.agent_service import read_skill, read_report


def get_history(aid: str) -> list:
    db = get_db()
    rows = db.execute(
        "SELECT role, content, ts FROM messages WHERE agent_id=? ORDER BY id",
        (aid,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


def clear_history(aid: str):
    db = get_db()
    db.execute("DELETE FROM messages WHERE agent_id=?", (aid,))
    db.commit()
    db.close()


def send_message(agent_id: str, message: str) -> str:
    db = get_db()
    db.execute(
        "INSERT INTO messages(agent_id, role, content) VALUES(?,?,?)",
        (agent_id, "user", message),
    )
    db.commit()

    if ANTHROPIC_API_KEY:
        try:
            import anthropic as ant

            skill = read_skill(agent_id)
            report = read_report(agent_id)
            system = (
                f"Voce e o agente '{agent_id}', um agente autonomo de IA pessoal. "
                f"Responda de forma concisa em portugues BR.\n\nSua configuracao:\n{skill[:3000]}"
            )
            if report:
                system += f"\n\nSeu ultimo relatorio:\n{json.dumps(report, ensure_ascii=False)[:1500]}"

            hist = db.execute(
                "SELECT role, content FROM messages WHERE agent_id=? ORDER BY id DESC LIMIT 20",
                (agent_id,),
            ).fetchall()
            messages = [{"role": r["role"], "content": r["content"]} for r in reversed(hist)]

            client = ant.Anthropic(api_key=ANTHROPIC_API_KEY)
            resp = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1024,
                system=system,
                messages=messages,
            )
            reply = resp.content[0].text
        except Exception as e:
            reply = f"Erro API: {e}"
    else:
        reply = (
            "Configure `ANTHROPIC_API_KEY` no arquivo `.env` para ativar o chat.\n\n"
            "Posso mostrar seus relatorios e configuracoes mesmo sem a chave!"
        )

    db.execute(
        "INSERT INTO messages(agent_id, role, content) VALUES(?,?,?)",
        (agent_id, "assistant", reply),
    )
    db.commit()
    db.close()
    return reply
