


(function() {
    const showHide = document.getElementById("show-hide-button");
    
    if (showHide) {
        const url = new URL(window.location.href);
        const hide = JSON.parse(sessionStorage.getItem("hide")) || {};

        function toggle() {
            hide[url.pth] = !hide[url.path];
            updateTable();
            sessionStorage.setItem("hide", JSON.stringify(hide));
            }

        function updateTable() {
            const deletedRows = document.querySelectorAll('tr.deleted');
            
            if (hide[url.path]) {
                showHide.innerHTML = showHide.dataset.hideText;
                for (var i = 0; i < deletedRows.length; ++i) {
                    deletedRows[i].classList.remove('hidden');
                    }
                }
            else {
                showHide.innerHTML = showHide.dataset.showText;
                for (var i = 0; i < deletedRows.length; ++i) {
                    deletedRows[i].classList.add('hidden');
                    }
                }            
            }
        
        updateTable();
        showHide.addEventListener('click', toggle);
        }
    
    
    
    const master = document.getElementById('master-checkbox');
    
    if (master) {
        function checkall(e) {
            const target = e.target;
            const checkboxes = document.querySelectorAll('input[type=checkbox]:enabled');
            
            for (var i = 0; i < checkboxes.length; ++i) {
                checkboxes[i].checked = target.checked;
                }
            }
        
        master.addEventListener('click', checkall);
        }
    
    })();
