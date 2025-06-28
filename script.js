// Navigation functionality
document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');
    const navLinks = document.querySelectorAll('.nav-link');

    // Mobile menu toggle
    hamburger.addEventListener('click', function() {
        hamburger.classList.toggle('active');
        navMenu.classList.toggle('active');
    });

    // Close mobile menu when link is clicked
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            hamburger.classList.remove('active');
            navMenu.classList.remove('active');
        });
    });

    // Smooth scrolling for navigation links
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetSection = document.querySelector(targetId);
            if (targetSection) {
                targetSection.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });

    // Jigsaw Puzzle Slideshow Animation
    const jigsawImages = document.querySelectorAll('.jigsaw-image');
    if (jigsawImages.length > 0) {
        let currentIndex = 0;
        
        function switchJigsawImage() {
            // Remove active class from current image
            jigsawImages[currentIndex].classList.remove('active');
            
            // Move to next image
            currentIndex = (currentIndex + 1) % jigsawImages.length;
            
            // Add active class to new image
            jigsawImages[currentIndex].classList.add('active');
        }
        
        // Switch images every 3 seconds
        setInterval(switchJigsawImage, 3000);
    }

    // Add scroll effect to navbar
    window.addEventListener('scroll', function() {
        const navbar = document.querySelector('.navbar');
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // Project card click navigation
    const projectCards = document.querySelectorAll('.project-card');
    projectCards.forEach((card, index) => {
        // Add click handler for project cards
        card.addEventListener('click', function(e) {
            // Don't trigger if clicking on overlay links
            if (!e.target.closest('.project-link')) {
                const projectLinks = [
                    'Projects/mitral-valve-segmentation.html', // Mitral Valve
                    'Projects/pde-neural-operators.html', // PDE identification
                    'Projects/jigsaw-puzzle.html', // Jigsaw Puzzle
                    '#'  // DFT calculation - placeholder
                ];
                
                if (projectLinks[index] && projectLinks[index] !== '#') {
                    window.location.href = projectLinks[index];
                }
            }
        });
        
        // Add cursor pointer to indicate clickability
        card.style.cursor = 'pointer';
    });
});