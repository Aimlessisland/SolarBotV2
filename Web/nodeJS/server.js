const express = require('express');
const path = require('path');
const app = express();
const PORT = 3000;

// Serve HTML files
app.use(express.static(path.join(__dirname, '../HTML')));

// Serve JS files so browser can fetch them via '../JS/...'
app.use('/JS', express.static(path.join(__dirname, '../JS')));

// Optional: Serve icons/images if needed
app.use('/ico', express.static(path.join(__dirname, '../ico')));

app.use('/CSS', express.static(path.join(__dirname,'../CSS')));

app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
});