


(function() {
    // Disable form submission after it has been submitted. This is just
    // to prevent double clicking of the submit button if the response is
    // slow for a better user experience and doess not obviate the need
    // for full server side validation to prevent duplicate posts.
    function submitHandler(e) {
        // Don't use e.target as the submit may be outside the form.
        const submits = document.querySelectorAll('input[type="submit"]');
        for (var i = 0; i < submits.length; ++i) {
            submits[i].setAttribute('disabled', true);
            }
        }

    const forms = document.querySelectorAll('form');
    for (var i = 0; i < forms.length; ++i) {
        forms[i].addEventListener('submit', submitHandler);
        }
    
    
    
    function invalidHandler(e) {
        e.target.classList.add('is-danger');
        }
    
    function inputHandler(e) {
        e.target.classList.remove('is-danger');
        }

    const inputs = document.querySelectorAll('input');
    for (var i = 0; i < inputs.length; ++i) {
        inputs[i].addEventListener('invalid', invalidHandler);
        inputs[i].addEventListener('input', inputHandler);
        }
    
    
    
    function insertField(element, data) {
        var root = element;
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
    
    function handleChange(e) {
        const url = new URL(window.location.href);
        url.searchParams.set(e.target.name, e.target.value);
        
        ajaxGet(url.href, insertField, e.target);
        }
    
    dynamics = inputs.querySelectorAll('.get-dynamic-fields');
    for (var i = 0; i < dynamics.length; ++i) {
        dynamics[i].addEventListener('change', handleChange);
        }

    })();


/*    

function openModal(identifier) {
    document.documentElement.classList.add("is-clipped");
    $(identifier).addClass("is-active");
    }


function closeModals() {
    document.documentElement.classList.remove("is-clipped");
    $(".modal").removeClass("is-active");
    }







$(".modal-close").on("click", closeModals);
*/

