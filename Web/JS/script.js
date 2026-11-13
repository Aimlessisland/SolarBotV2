const API_URL = `http://${window.location.hostname}:5000/cmd`;
let activeHoldCmd = null;

async function sendOnce(cmd) {
    try {
        const res = await fetch(`${API_URL}?c=${encodeURIComponent(cmd)}`);
        return res.ok;
    } catch (e) {
        return false;
    }
}

function bindHoldButton(btn, cmd) {
    if (!btn) return;
    btn.style.touchAction = "none";

    const startHold = async (e) => {
        e.preventDefault();
        if (activeHoldCmd === cmd) return;
        activeHoldCmd = cmd;

        while (activeHoldCmd === cmd) {
            const gotOk = await sendOnce(cmd);
            if (!gotOk) break;
        }
    };

    const stopHold = () => {
        if (activeHoldCmd === cmd) {
            activeHoldCmd = null;
            sendOnce("M0 0");
        }
    };

    btn.addEventListener("pointerdown", startHold);
    btn.addEventListener("pointerup", stopHold);
    btn.addEventListener("pointerleave", stopHold);
    btn.addEventListener("pointercancel", stopHold);
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
            activeHoldCmd = null;
            sendOnce("M0 0");
        });
    }

    const wideBtn = document.querySelector(".wide-btn");
    let isRunning = false;
    if (wideBtn) {
        wideBtn.addEventListener("click", () => {
            activeHoldCmd = null;
            isRunning = !isRunning;
            sendOnce(isRunning ? "M20 100" : "M0 0");
        });
    }
});