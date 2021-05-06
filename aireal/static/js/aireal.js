function navigate(href) {
        var url = new URL(href, window.location.href);
        if (url.pathname == "/back") {
            var navstack = JSON.parse(sessionStorage.getItem("navstack"));
            if (navstack === null || !navstack.length) {
                url = new URL("/", window.location.href);
                navstack = [url.href];
                }
            href = navstack[navstack.length - 1];
            }
        window.location.replace(href);
        }


function navigateHandler(e) {
    e.preventDefault();
    navigate(e.currentTarget.href);
    }


function defer(func) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', func);
        }
    else {  // `DOMContentLoaded` has already fired
        func();
        }
    }


function openModal(identifier) {
    document.documentElement.classList.add("is-clipped");
    $(identifier).addClass("is-active");
    }


function closeModals() {
    document.documentElement.classList.remove("is-clipped");
    $(".modal").removeClass("is-active");
    }


defer (function() {
    if (document.referrer) {
        var url = new URL(window.location.href);
        var dir = url.searchParams.get("dir");
        var referrer = new URL(document.referrer);
        if (dir && url.pathname != referrer.pathname) {
            var navstack = JSON.parse(sessionStorage.getItem("navstack"));
            if (navstack === null) {
                navstack = [];
                }
            else if (navstack.length > 9) {
                navstack.shift();
                }
            
            if (dir == "1") {
                referrer.searchParams.set("dir", "-1");
                navstack.push(referrer.href);
                }
            else if (dir == "-1") {
                navstack.pop();
                }
            
            sessionStorage.setItem("navstack", JSON.stringify(navstack));
            }
        }
    
    
    const anchors = document.querySelectorAll('a[href]');
    for (var i = 0; i < anchors.length; ++i) {
        anchors[i].addEventListener('click', navigateHandler);
        }
    
    // Only allow a form to be submitted once. Should have sufficient logic
    // to prevent dara corruption if multiple submissions but this ensures
    // that the response the user sees reflects the first submission.
    $('form').one('submit', function() {
        var navstack = JSON.parse(sessionStorage.getItem("navstack"));
        if (navstack !== null && navstack.length) {
            $(this).children('input[name="back"]').val(navstack[navstack.length - 1]);
            }
        $(this).children('input[type="submit"]').attr('disabled', true);
        return true;
        });


    // Lazy load dropdown menus.
    $('.has-dropdown').one('mouseenter', function() {
        $(this).children('.navbar-dropdown').load($(this).attr('data-href'));
        return true;
        });

    
    // Prevent accidental dragging of elements as looks ugly.
    $('body').on('ondragstart', function() {
        return false;
        });
    
    
    $(".modal-close").on("click", closeModals);
    
    
    $("input").on("invalid", function() {
        $(this).addClass("is-danger");
        });
    
    
    $("input").on("input", function() {
        $(this).removeClass("is-danger");
        });
    
    $(".get-dynamic-fields").on("change", function() {
        function swapFields(data, textStatus, jqXHR) {
            var root = this;
            while (root.parentElement.nodeName != 'FORM') {
                root = root.parentElement;
                if (root == null) {
                    return;
                    }
                }
            
            var elem = root.nextSibling;
            while (elem !== null && (elem.nodeName == '#text' || elem.nodeName == 'DIV')) {
                var unwanted = elem;
                elem = elem.nextSibling;
                unwanted.remove();
                }
            
            root.insertAdjacentHTML('afterend', data);
            }
        
        var url = new URL(window.location.href);
        url.searchParams.set(this.name, this.value);
        $.ajax({url: url.href,
                context: this,
                success: swapFields});
        });
    
    });



