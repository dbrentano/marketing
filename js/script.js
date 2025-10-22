        let lastScrollY = window.scrollY;
        const header = document.querySelector('header.nav');
        let ticking = false;

        function updateHeader() {
            const currentY = window.scrollY;

            if (currentY > lastScrollY && currentY > 100) {
                // Scrolling down — hide header
                header.classList.add('hide-header');
            } else {
                // Scrolling up — show header
                header.classList.remove('hide-header');
            }

            lastScrollY = currentY;
            ticking = false;
        }

        window.addEventListener('scroll', () => {
            if (!ticking) {
                window.requestAnimationFrame(updateHeader);
                ticking = true;
            }
        });

        const menuToggle = document.querySelector('.menu-toggle');
        const navLinks = document.querySelector('.nav-links');

        if (menuToggle && navLinks) {
            menuToggle.addEventListener('click', () => {
                const isOpen = menuToggle.classList.toggle('open');
                navLinks.classList.toggle('show', isOpen);
                menuToggle.setAttribute('aria-expanded', isOpen);
            });

            // Close menu when clicking a link
            navLinks.querySelectorAll('a').forEach(link => {
                link.addEventListener('click', () => {
                    menuToggle.classList.remove('open');
                    navLinks.classList.remove('show');
                    menuToggle.setAttribute('aria-expanded', 'false');
                });
            });
        }
function handleSubmit(event) {
    event.preventDefault();
    const form = event.target;

    // Send the form to Netlify
    fetch("/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams(new FormData(form)).toString(),
    })
        .then(() => {
            document.getElementById("form-content").style.display = "none";
            document.getElementById("thank-you").style.display = "block";
        })
        .catch((error) => alert("Something went wrong. Please try again."));
}
        document.getElementById("year").textContent = new Date().getFullYear();