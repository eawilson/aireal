


(function() {
    const showHide = document.getElementById("show-hide-button");
    
    if (showHide) {
        const url = new URL(window.location.href);
        const hide = JSON.parse(sessionStorage.getItem("hide")) || {};

        function toggleShowHide() {
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
        showHide.addEventListener('click', toggleShowHide);
        }
    
    
    
    const master = document.getElementById('master-checkbox');
    const checkBoxes = document.querySelectorAll('input[type=checkbox]:enabled');
   
    if (master) {
        function toggleSubmit(e) {
            for (var i = 0; i < checkBoxes.length; ++i) {
                if (checkBoxes[i].checked) {
                    document.getElementById('submit-button').disabled = false;
                    return;
                    }
                document.getElementById('submit-button').disabled = true;
                }
            }
        
        function checkall(e) {
            const target = e.target;
            
            for (var i = 0; i < checkBoxes.length; ++i) {
                checkBoxes[i].checked = target.checked;
                }
            
            toggleSubmit();
            }
        
        for (var i = 0; i < checkBoxes.length; ++i) {
            if (checkBoxes[i] === master) {
                checkBoxes[i].addEventListener('change', checkall);
                }
            else {
                checkBoxes[i].addEventListener('change', toggleSubmit);
                }
                
            }

        toggleSubmit();
        }
    
    })();
