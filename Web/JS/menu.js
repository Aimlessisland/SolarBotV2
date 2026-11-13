document.addEventListener('DOMContentLoaded', () => {
    const menuButton = document.getElementById('menuButton');

    if (!menuButton) return;

    menuButton.addEventListener('click', () => {
        const existingBtn1 = document.getElementById('subButton1');

        if (existingBtn1) {
            const subBtns = [
                document.getElementById('subButton1'),
                document.getElementById('subButton2'),
                document.getElementById('subButton3')
            ];

            subBtns.forEach((btn) => {
                if (btn) {
                    btn.style.right = '24px';
                    btn.style.opacity = '0';
                    setTimeout(() => btn.remove(), 400);
                }
            });
            return;
        }

        const targets = ['120px', '216px', '312px'];
        const labels = ['Device', 'Control', 'Detail'];

        targets.forEach((targetRight, index) => {
            const subBtn = document.createElement('button');
            const label = labels[index];
            
            subBtn.id = `subButton${index + 1}`;
            subBtn.textContent = label;
            subBtn.className = menuButton.className;
            
            // 1. Check if this button corresponds to the current page
            const isCurrentPage = (label === 'Detail' && window.location.pathname.includes('deviceDetail.html')) ||
                                  (label === 'Control' && window.location.pathname.includes('controllerPage.html')) ||
                                  (label === 'Device' && window.location.pathname.includes('addDevice.html'));

            subBtn.style.position = 'fixed';
            subBtn.style.bottom = '24px';
            subBtn.style.right = '24px';
            subBtn.style.zIndex = '9998';
            subBtn.style.opacity = '0';
            
            // 2. Set orange if active, grey if inactive
            subBtn.style.backgroundColor = isCurrentPage ? '#ea580c' : '#aaa7a7';
            
            subBtn.style.transition = 'right 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease';

            // 3. Add navigation action on click
            subBtn.onclick = () => {
                if (label === 'Detail') {
                    window.location.href = 'deviceDetail.html';
                } else if (label === 'Control') {
                    window.location.href = 'controllerPage.html';
                } else if (label === 'Device') {
                    window.location.href = 'addDevice.html';
                }
            };

            document.body.appendChild(subBtn);
            subBtn.offsetHeight;

            setTimeout(() => {
                subBtn.style.right = targetRight;
                subBtn.style.opacity = '1';
            }, index * 450);
        });
    });
});