const API_URL = `http://${window.location.hostname}:5000/cmd`;
let pressedCmd = null;

async function sendOnce(cmd) {
    try {
        const res = await fetch(`${API_URL}?c=${encodeURIComponent(cmd)}`);
        const reply = (await res.text()).trim();
        return res.ok && reply === "OK";
    } catch (e) {
        return false;
    }
}

function bindHoldButton(btn, cmd) {
    if (!btn) return;
    btn.style.touchAction = "none";

    btn.addEventListener("pointerdown", async (e) => {
        e.preventDefault();
        if (pressedCmd === cmd) return;
        pressedCmd = cmd;

        // Loop only while this button is still pressed AND previous pulse returned OK
        while (pressedCmd === cmd) {
            const gotOk = await sendOnce(cmd);
            if (!gotOk) break;
        }
    });

    // Clear flag on release so the loop stops naturally on the next check
    const release = () => {
        if (pressedCmd === cmd) {
            pressedCmd = null;
        }
    };

    btn.addEventListener("pointerup", release);
    btn.addEventListener("pointerleave", release);
    btn.addEventListener("pointercancel", release);
    btn.addEventListener("contextmenu", (e) => e.preventDefault());
}

window.addEventListener("DOMContentLoaded", () => {
    const arrowMap = {
        "←": "M3 100",
        "↑": "M1 100",
        "↓": "M2 100",
        "→": "M4 100"
    };

    document.querySelectorAll(".dpad-row .control-btn").forEach((btn) => {
        const cmd = arrowMap[btn.textContent.trim()];
        if (cmd) bindHoldButton(btn, cmd);
    });

    const powerBtn = document.querySelector(".power-btn");
    if (powerBtn) {
        powerBtn.addEventListener("click", () => {
            pressedCmd = null;
            sendOnce("M0 0");
        });
    }

    const wideBtn = document.querySelector(".wide-btn");
    let isRunning = false;
    if (wideBtn) {
        wideBtn.addEventListener("click", () => {
            pressedCmd = null;
            isRunning = !isRunning;
            sendOnce(isRunning ? "M20 100" : "M0 0");
        });
    }
});