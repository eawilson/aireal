


(function() {
    var activeMenu = null;
    var activeRow = null;
        
    function showTableMenu(e) {
        var row = intendedTarget(e, 'TR');
        if (!row) {
            return;
            }
        
        const menuId = row.parentElement.dataset.menuId;
        const menu = document.getElementById(menuId);

        // Some other menu is active therefore allow event to bubble and hide it
        if (activeMenu && !menu.isSameNode(activeMenu)) {
            return;
            }
        
        e.preventDefault();
        e.stopPropagation(); // If allowed to bubble will close menu
        
        const menuItems = itemsFromMenu(menu);
        for (var i = 0; i < menuItems.length; ++i) {
            var menuItem = menuItems[i];
            menuItem.style.display = itemIsEnabled(menuItem, row) ? 'block' : 'none';
            }
        
        //menu.style.display = 'block';
        menu.classList.add('is-active');
        menu.hidden = false;
        
        var top = e.pageY;
        var left = e.pageX;
        const maxY = window.scrollY + window.innerHeight;
        const maxX = window.scrollX + window.innerWidth;
        const menuHeight = menu.scrollHeight;
        const menuWidth = menu.scrollWidth;

        if (top + menuHeight > maxY) {
            top = Math.max(top - menuHeight, 0);
            }

        if (left + menuWidth > maxX) {
            left = Math.max(left - menuWidth, 0);
            }
        
        window.addEventListener('resize', hideTableMenu);
        document.addEventListener('contextmenu', hideTableMenu);
        document.addEventListener('click', hideTableMenu);
        document.addEventListener('keyup', hideTableMenu);
        
        menu.style.top = top + 'px';
        menu.style.left = left + 'px';
        menu.style.position = 'absolute';
        menu.style.zIndex = 10;
        activeMenu = menu;
        activeRow = row;
        }
    
    
    function hideTableMenu(e) {
        if (e.keyCode && e.keyCode != 27) {
            return;
            }
        
        window.removeEventListener('resize', hideTableMenu);
        document.removeEventListener('contextmenu', hideTableMenu);
        document.removeEventListener('click', hideTableMenu);
        document.removeEventListener('keyup', hideTableMenu);
        
        //activeMenu.style.display = 'none';
        activeMenu.classList.remove('is-active');
        activeMenu = null;
        activeRow = null;
        }
    
    
    function clickTable(e) {
        var row = intendedTarget(e, 'TR');
        if (!row) {
            return;
            }
                
        const menuId = row.parentElement.dataset.menuId;
        const menu = document.getElementById(menuId);
        const menuItem = itemsFromMenu(menu)[0];
        
        if (itemIsEnabled(menuItem, row)) {
            activeRow = row;
            clickMenu({'currentTarget': menuItem});
            }
        }
    
    
    function clickMenu(e) {
        const menuItem = e.currentTarget;
        const url = new URL(menuItem.dataset.href, window.location.href);
        url.pathname = url.pathname.replace(/\/0$/, '/' + activeRow.dataset.id);
        url.pathname = url.pathname.replace(/\/0\//, '/' + activeRow.dataset.id + '/');
        
        if (typeof e.preventDefault === 'function') {
            e.preventDefault();
            }
        
        if (menuItem.dataset.method == "POST") {
            const action = document.getElementById("action");
            action.value = menuItem.textContent;
            const form = document.getElementById("table-form");
            form.action = url.href;
            form.submit();
            }
        else {
            navigate(url.href);
            }
        }
    
    
    function intendedTarget(e, tagName) {
        var target = e.target;
        while (target && target.tagName != tagName) {
            target = target.parentElement;
            }
            return target;
        }
    
    
    function itemIsEnabled(menuItem, row) {
        const visibleIf = menuItem.dataset.visibleIf;
        if (!(visibleIf)) {
            return true;
            }
        
        if (visibleIf.startsWith('!')) {
            return !row.classList.contains(visibleIf.substring(1));
            }
        else {
            return row.classList.contains(visibleIf);
            }
        }
    
    
    function itemsFromMenu(menu) {
        return menu.querySelectorAll('a');
        }
    
    
    function preventDefault(e) {
        e.preventDefault();
        }
    
    
//     document.addEventListener('contextmenu', preventDefault);
    
    const tbodies = document.getElementsByTagName('tbody');
    for(var i = 0; i < tbodies.length; ++i) {
        var tbody = tbodies[i];
        if ('menuId' in tbody.dataset) {
            tbody.addEventListener('contextmenu', showTableMenu);
            tbody.addEventListener('click', clickTable);
            tbody.classList.add('is-clickable');
            
            var menu = document.getElementById(tbody.dataset.menuId);
            var menuItems = itemsFromMenu(menu);
            for (var i = 0; i < menuItems.length; ++i) {
                menuItems[i].addEventListener('click', clickMenu);
                }
            }
        }
    })();


