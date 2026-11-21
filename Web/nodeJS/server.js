
const express = require('express');
const path = require('path');
const fs = require('fs/promises'); /* ใช้อ่านไฟล์จากโฟลเดอร์โดยตรง */

const app = express();
const PORT = 3000;

// Serve HTML files
app.use(express.static(path.join(__dirname, '../HTML')));

// Serve JS files so browser can fetch them via '../JS/...'
app.use('/JS', express.static(path.join(__dirname, '../JS')));

// Optional: Serve icons/images if needed
app.use('/ico', express.static(path.join(__dirname, '../ico')));

app.use('/CSS', express.static(path.join(__dirname, '../CSS')));


/* ระบุตำแหน่งโฟลเดอร์ภาพโดยตรง */
const IMG_DIR = path.resolve(
    __dirname,
    '../../Linux/solarBot/imgForward'
);

/* ค้นหาและส่งภาพล่าสุด */
app.get('/api/latest-camera', async (req, res) => {
    try {
        /* อ่านรายชื่อไฟล์ใน imgForward */
        const entries = await fs.readdir(IMG_DIR, {
            withFileTypes: true
        });

        /* เลือกเฉพาะไฟล์ภาพ */
        const files = entries
            .filter(file =>
                file.isFile() &&
                /\.(jpg|jpeg|png|webp|bmp|gif)$/i.test(file.name)
            )
            .map(file => file.name);

        if (files.length == 0) {
            return res.status(404).send("No images");
        }

        /* เปลี่ยน -> ใช้เวลาเปลี่ยนสถานะไฟล์ล่าสุด
           แทนเวลาแก้ไขเนื้อหาของภาพ */
        const images = await Promise.all(
            files.map(async (name) => {
                const stat = await fs.stat(path.join(IMG_DIR, name));
                return {
                    name,
                    time: stat.ctimeMs // เปลี่ยนจาก mtimeMs เป็น ctimeMs
                };
            })
        );

        /* เรียงภาพใหม่ที่สุดขึ้นก่อน */
        images.sort((a, b) => b.time - a.time);

        /* ส่งภาพล่าสุดให้ HTML โดยตรง */
        res.setHeader("Cache-Control", "no-store");
        res.sendFile(path.join(IMG_DIR, images[0].name));

    } catch (err) {
        console.error("Camera error:", err.message);
        res.status(500).send("Camera unavailable");
    }
});


app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
});
