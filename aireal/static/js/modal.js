
(function() {

    function openModal() {
        document.documentElement.classList.add("is-clipped");
        document.getElementById('modal').classList.add("is-active");
        }
    
    function closeModal() {
        document.documentElement.classList.remove("is-clipped");
        document.getElementById('modal').classList.remove("is-active");
        }
        
    function openHandler(e) {
        openModal();
        e.preventDefault();
        }
    
    function closeHandler(e) {
        closeModal();
        e.preventDefault();
        }
    
    document.getElementById('submit-button').addEventListener('click', openHandler);
    document.getElementById('modal-cancel').addEventListener('click', closeHandler);
    document.getElementById('modal-background').addEventListener('click', closeHandler);
    
    })();
    
