    
(function() {
    
    function performUpdate(table, responseText) {
        const texts = JSON.parse(responseText);
        const key = table.dataset.autoupdateKey;
        const value = table.dataset.autoupdateValue;
        const rows = table.rows;
        
        for (var i = 1; i < rows.length; ++i) {
            var row = rows[i];
            var newText = texts[row.cells[key].textContent];
            if (newText === undefined) {
                newText = '';
                }
            row.cells[value].textContent = newText;
            }
        }
    
    const tables = document.querySelectorAll('table.autoupdate');
    for(var i = 0; i < tables.length; ++i) {
        const table = tables[i];
        setInterval(ajaxGet, table.dataset.autoupdateMiliseconds, table.dataset.autoupdateHref, performUpdate, table);
        }
        
    })();



