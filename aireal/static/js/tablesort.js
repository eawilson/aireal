


(function() {
    function ancestorByTag(element, tagName) {
        var target = element;
        while (target && target.tagName != tagName) {
            target = target.parentElement;
            }
            return target;
        }


    function compareAsc(a, b) {
        return (a[0] > b[0]) ? 1 : (a[0] < b[0]) ? -1 : 0;
        }


    function compareDesc(a, b) {
        return (a[0] < b[0]) ? 1 : (a[0] > b[0]) ? -1 : 0;
        }


    function sortHandler(e) {
        const clickedCell = ancestorByTag(e.target, 'TH');
        
        if (!clickedCell.innerText) {
            return;
            }
        
        const tbody = ancestorByTag(clickedCell ,'TABLE').querySelector('tbody');
        const sortClass = clickedCell.classList.contains('sorted-asc') ? 'sorted-desc' : 'sorted-asc';
        
        const headerCells = clickedCell.parentElement.children;
        var columnIndex = null;
        for (var i = 0; i < headerCells.length; ++i) {
            var headerCell = headerCells[i];
            headerCell.classList.remove('sorted-desc');
            headerCell.classList.remove('sorted-asc');
            headerCell.classList.remove('unsorted');
            if  (headerCell.isSameNode(clickedCell)) {
                columnIndex = i;
                headerCell.classList.add(sortClass);
                }
            else {
                headerCell.classList.add('unsorted');
                }
            }
        
        const rows = tbody.children;
        const data = [];
        
        for (var i = 0; i < rows.length; ++i) {
            var row = rows[i];
            var cell = row.children[columnIndex];
            var value = 'sortValue' in cell.dataset ? cell.dataset.sortValue : cell.textContent;
            data.push([value, row]);
            }
        
        data.sort((sortClass == 'sorted-asc') ? compareAsc : compareDesc);
        for (var i = 0; i < data.length; ++i) {
            tbody.append(data[i][1]);
            }
        }
    
    
    const theads = document.querySelectorAll('thead.is-sortable');
    for(var i = 0; i < theads.length; ++i) {
        var thead = theads[i];
        var headerCells = thead.querySelector('tr').children;
        
        thead.addEventListener('click', sortHandler);
        for (var i = 0; i < headerCells.length; ++i) {
            headerCells[i].classList.add('unsorted');
            }
        }
    })();

    
    
    
    
    
    
