/* =========================================
   SECTION 1: API COMMUNICATION จัดการการส่งคำสั่งไปยังหุ่นยนต์
   ========================================= */

   const API_URL = `http://${window.location.hostname}:5000/cmd`;

   let pressedCmd = null;
   let isPowerOff = true; /* เริ่มต้นล็อกปุ่มเดินไว้ก่อน จนกว่าจะกด Start */
   
   async function sendOnce(cmd) {
       try {
           const res = await fetch(`${API_URL}?c=${encodeURIComponent(cmd)}`);
           const reply = (await res.text()).trim();
           return res.ok && reply === "OK";
       } catch (e) {
           return false;
       }
   }
   
   
   /* =========================================
      SECTION 2: HOLD BUTTON จัดการการกดปุ่มทิศทางค้างไว้
      ========================================= */
   
   function bindHoldButton(btn, cmd) {
       if (!btn) return;
       btn.style.touchAction = "none";
   
       btn.addEventListener("pointerdown", async (e) => {
           e.preventDefault();
   
           /* ไม่อนุญาตให้กดเดินขณะ Power Off */
           if (isPowerOff) return;
   
           if (pressedCmd === cmd) return;
           pressedCmd = cmd;
   
           btn.classList.add("is-pressed");
   
           /* หยุด Loop หากอยู่ในสถานะ Power Off */
           while (pressedCmd === cmd && !isPowerOff) {
               const gotOk = await sendOnce(cmd);
               if (!gotOk) break;
           }
       });
   
       const release = () => {
           if (pressedCmd === cmd) {
               pressedCmd = null;
           }
           btn.classList.remove("is-pressed");
       };
   
       btn.addEventListener("pointerup", release);
       btn.addEventListener("pointerleave", release);
       btn.addEventListener("pointercancel", release);
       btn.addEventListener("contextmenu", (e) => e.preventDefault());
   }
   
   
   /* =========================================
      SECTION 3: DIRECTION CONTROLS กำหนดคำสั่งควบคุมทิศทาง
      ========================================= */
   
   window.addEventListener("DOMContentLoaded", () => {
   
       const arrowMap = {
           "Left": "M3 100",
           "Up": "M1 100",
           "Down": "M2 100",
           "Right": "M4 100"
       };
   
       document.querySelectorAll(".dpad-row .control-btn").forEach((btn) => {
           const img = btn.querySelector("img");
           const direction = img ? img.alt : btn.textContent.trim();
           const cmd = arrowMap[direction];
   
           if (cmd) bindHoldButton(btn, cmd);
       });
   
   
       /* =========================================
          SECTION 4: POWER OFF จัดการการหยุดและล็อกปุ่มเดิน
          ========================================= */
   
       const powerBtn = document.querySelector(".power-btn");
       const wideBtn = document.querySelector(".wide-btn");
       let isRunning = false;
   
       if (powerBtn) {
           powerBtn.addEventListener("click", () => {
               /* เปิดสถานะล็อกปุ่มเดิน */
               isPowerOff = true;
               pressedCmd = null;
   
               /* คืนสีเทาให้ปุ่มลูกศรทั้งหมดทันที */
               document.querySelectorAll(".dpad-row .control-btn")
                   .forEach((btn) => {
                       btn.classList.remove("is-pressed");
                   });
   
               /* ส่ง STOP เพื่อหยุดทั้ง Full Clean ('f' mode) และมอเตอร์ทั้งหมด */
               sendOnce("STOP");
   
               /* เปลี่ยน Power Off เป็นสีแดง */
               powerBtn.classList.add("is-off");
   
               /* รีเซ็ตสถานะ Start | Break */
               isRunning = false;
   
               /* คืนปุ่ม Start | Break เป็นสีเทา */
               if (wideBtn) {
                   wideBtn.classList.remove("is-running", "is-break");
               }
           });
       }
   
   
       /* =========================================
          SECTION 5: START & BREAK จัดการเริ่มและหยุดการทำงาน
          ========================================= */
   
       if (wideBtn) {
           wideBtn.addEventListener("click", () => {
               pressedCmd = null;
               isRunning = !isRunning;
   
               /* ปลดล็อกปุ่มเดินเมื่อกด Start */
               if (isRunning) {
                   isPowerOff = false;
               }
   
               /* ส่ง START เพื่อเริ่ม Full Clean ('f') หรือ BREAK เพื่อหยุดชั่วคราว */
               sendOnce(isRunning ? "START" : "BREAK");
   
               /* Start สีเขียว / Break สีส้ม */
               wideBtn.classList.toggle("is-running", isRunning);
               wideBtn.classList.toggle("is-break", !isRunning);
   
               /* คืน Power Off เป็นสีเทา */
               if (powerBtn) {
                   powerBtn.classList.remove("is-off");
               }
           });
       }
   
   });