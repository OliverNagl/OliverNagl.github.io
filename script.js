// Mobile Navigation Toggle
const hamburger = document.querySelector('.hamburger');
const navMenu = document.querySelector('.nav-menu');

hamburger.addEventListener('click', () => {
    hamburger.classList.toggle('active');
    navMenu.classList.toggle('active');
});

// Close mobile menu when clicking on a link
document.querySelectorAll('.nav-link').forEach(n => n.addEventListener('click', () => {
    hamburger.classList.remove('active');
    navMenu.classList.remove('active');
}));

// Smooth Scrolling
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Navbar Background on Scroll
window.addEventListener('scroll', () => {
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 100) {
        navbar.style.background = 'rgba(255, 255, 255, 0.98)';
        navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
    } else {
        navbar.style.background = 'rgba(255, 255, 255, 0.95)';
        navbar.style.boxShadow = 'none';
    }
});

// Molecular Background Animation
class MolecularBackground {
    constructor() {
        this.canvas = document.getElementById('moleculeCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.molecules = [];
        this.animationId = null;
        
        this.init();
    }
    
    init() {
        this.resize();
        this.createMolecules();
        this.animate();
        
        window.addEventListener('resize', () => this.resize());
        window.addEventListener('mousemove', (e) => this.handleMouseMove(e));
    }
    
    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }
    
    createMolecules() {
        const numberOfMolecules = Math.floor((this.canvas.width * this.canvas.height) / 15000);
        
        for (let i = 0; i < numberOfMolecules; i++) {
            this.molecules.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                radius: Math.random() * 3 + 1,
                connections: [],
                color: this.getRandomAtomColor(),
                pulse: Math.random() * Math.PI * 2
            });
        }
        
        // Create connections between nearby molecules
        this.molecules.forEach((molecule, i) => {
            this.molecules.slice(i + 1).forEach((otherMolecule, j) => {
                const distance = this.getDistance(molecule, otherMolecule);
                if (distance < 100) {
                    molecule.connections.push(i + j + 1);
                }
            });
        });
    }
    
    getRandomAtomColor() {
        const colors = [
            '#4f46e5', // Carbon (blue/purple)
            '#059669', // Nitrogen (green)
            '#dc2626', // Oxygen (red)
            '#eab308', // Sulfur (yellow)
            '#7c3aed', // Generic (purple)
            '#0891b2'  // Generic (cyan)
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }
    
    getDistance(mol1, mol2) {
        return Math.sqrt(Math.pow(mol1.x - mol2.x, 2) + Math.pow(mol1.y - mol2.y, 2));
    }
    
    handleMouseMove(e) {
        const mouseX = e.clientX;
        const mouseY = e.clientY;
        
        this.molecules.forEach(molecule => {
            const distance = Math.sqrt(Math.pow(mouseX - molecule.x, 2) + Math.pow(mouseY - molecule.y, 2));
            if (distance < 150) {
                const force = (150 - distance) / 150;
                const angle = Math.atan2(molecule.y - mouseY, molecule.x - mouseX);
                molecule.vx += Math.cos(angle) * force * 0.02;
                molecule.vy += Math.sin(angle) * force * 0.02;
            }
        });
    }
    
    updateMolecules() {
        this.molecules.forEach(molecule => {
            // Update position
            molecule.x += molecule.vx;
            molecule.y += molecule.vy;
            
            // Boundary checks with wrapping
            if (molecule.x < 0) molecule.x = this.canvas.width;
            if (molecule.x > this.canvas.width) molecule.x = 0;
            if (molecule.y < 0) molecule.y = this.canvas.height;
            if (molecule.y > this.canvas.height) molecule.y = 0;
            
            // Apply friction
            molecule.vx *= 0.99;
            molecule.vy *= 0.99;
            
            // Update pulse for glow effect
            molecule.pulse += 0.02;
        });
    }
    
    drawMolecules() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw connections first
        this.molecules.forEach((molecule, i) => {
            molecule.connections.forEach(connectionIndex => {
                if (connectionIndex < this.molecules.length) {
                    const connected = this.molecules[connectionIndex];
                    const distance = this.getDistance(molecule, connected);
                    
                    if (distance < 120) {
                        this.ctx.strokeStyle = `rgba(255, 255, 255, ${0.3 * (1 - distance / 120)})`;
                        this.ctx.lineWidth = 1;
                        this.ctx.beginPath();
                        this.ctx.moveTo(molecule.x, molecule.y);
                        this.ctx.lineTo(connected.x, connected.y);
                        this.ctx.stroke();
                    }
                }
            });
        });
        
        // Draw molecules
        this.molecules.forEach(molecule => {
            const glowSize = molecule.radius + Math.sin(molecule.pulse) * 2;
            
            // Glow effect
            const gradient = this.ctx.createRadialGradient(
                molecule.x, molecule.y, 0,
                molecule.x, molecule.y, glowSize * 3
            );
            gradient.addColorStop(0, molecule.color + '80');
            gradient.addColorStop(0.5, molecule.color + '20');
            gradient.addColorStop(1, molecule.color + '00');
            
            this.ctx.fillStyle = gradient;
            this.ctx.beginPath();
            this.ctx.arc(molecule.x, molecule.y, glowSize * 3, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Core molecule
            this.ctx.fillStyle = molecule.color;
            this.ctx.beginPath();
            this.ctx.arc(molecule.x, molecule.y, molecule.radius, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Highlight
            this.ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
            this.ctx.beginPath();
            this.ctx.arc(
                molecule.x - molecule.radius * 0.3,
                molecule.y - molecule.radius * 0.3,
                molecule.radius * 0.3,
                0,
                Math.PI * 2
            );
            this.ctx.fill();
        });
    }
    
    animate() {
        this.updateMolecules();
        this.drawMolecules();
        this.animationId = requestAnimationFrame(() => this.animate());
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
}

// Protein-Ligand Interaction Visualization
class ProteinLigandVisualization {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;
        
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');
        this.container.appendChild(this.canvas);
        
        this.protein = {
            x: 150,
            y: 150,
            radius: 80,
            binding_sites: []
        };
        
        this.ligand = {
            x: 50,
            y: 50,
            radius: 15,
            vx: 1,
            vy: 1,
            bound: false
        };
        
        this.init();
    }
    
    init() {
        this.resize();
        this.createBindingSites();
        this.animate();
        
        window.addEventListener('resize', () => this.resize());
    }
    
    resize() {
        this.canvas.width = 300;
        this.canvas.height = 300;
    }
    
    createBindingSites() {
        for (let i = 0; i < 5; i++) {
            const angle = (i / 5) * Math.PI * 2;
            this.protein.binding_sites.push({
                x: this.protein.x + Math.cos(angle) * 60,
                y: this.protein.y + Math.sin(angle) * 60,
                radius: 10,
                occupied: false,
                affinity: Math.random()
            });
        }
    }
    
    updateLigand() {
        if (!this.ligand.bound) {
            this.ligand.x += this.ligand.vx;
            this.ligand.y += this.ligand.vy;
            
            // Boundary checks
            if (this.ligand.x < this.ligand.radius || this.ligand.x > this.canvas.width - this.ligand.radius) {
                this.ligand.vx *= -1;
            }
            if (this.ligand.y < this.ligand.radius || this.ligand.y > this.canvas.height - this.ligand.radius) {
                this.ligand.vy *= -1;
            }
            
            // Check for binding
            this.protein.binding_sites.forEach(site => {
                if (!site.occupied) {
                    const distance = Math.sqrt(
                        Math.pow(this.ligand.x - site.x, 2) + 
                        Math.pow(this.ligand.y - site.y, 2)
                    );
                    
                    if (distance < site.radius + this.ligand.radius && Math.random() < site.affinity * 0.01) {
                        this.ligand.bound = true;
                        this.ligand.x = site.x;
                        this.ligand.y = site.y;
                        site.occupied = true;
                        
                        // Unbind after some time
                        setTimeout(() => {
                            this.ligand.bound = false;
                            site.occupied = false;
                            this.ligand.vx = (Math.random() - 0.5) * 3;
                            this.ligand.vy = (Math.random() - 0.5) * 3;
                        }, 2000 + Math.random() * 3000);
                    }
                }
            });
        }
    }
    
    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw protein
        this.ctx.fillStyle = 'rgba(79, 70, 229, 0.3)';
        this.ctx.beginPath();
        this.ctx.arc(this.protein.x, this.protein.y, this.protein.radius, 0, Math.PI * 2);
        this.ctx.fill();
        
        this.ctx.strokeStyle = '#4f46e5';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
        
        // Draw binding sites
        this.protein.binding_sites.forEach(site => {
            this.ctx.fillStyle = site.occupied ? '#dc2626' : '#059669';
            this.ctx.beginPath();
            this.ctx.arc(site.x, site.y, site.radius, 0, Math.PI * 2);
            this.ctx.fill();
        });
        
        // Draw ligand
        this.ctx.fillStyle = this.ligand.bound ? '#eab308' : '#7c3aed';
        this.ctx.beginPath();
        this.ctx.arc(this.ligand.x, this.ligand.y, this.ligand.radius, 0, Math.PI * 2);
        this.ctx.fill();
        
        // Glow effect for ligand
        const gradient = this.ctx.createRadialGradient(
            this.ligand.x, this.ligand.y, 0,
            this.ligand.x, this.ligand.y, this.ligand.radius * 2
        );
        gradient.addColorStop(0, (this.ligand.bound ? '#eab308' : '#7c3aed') + '40');
        gradient.addColorStop(1, (this.ligand.bound ? '#eab308' : '#7c3aed') + '00');
        
        this.ctx.fillStyle = gradient;
        this.ctx.beginPath();
        this.ctx.arc(this.ligand.x, this.ligand.y, this.ligand.radius * 2, 0, Math.PI * 2);
        this.ctx.fill();
    }
    
    animate() {
        this.updateLigand();
        this.draw();
        requestAnimationFrame(() => this.animate());
    }
}

// Intersection Observer for Scroll Animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.animationPlayState = 'running';
        }
    });
}, observerOptions);

// Observe elements for scroll animations
document.addEventListener('DOMContentLoaded', () => {
    const animatedElements = document.querySelectorAll('.about-card, .stat-card, .project-card');
    animatedElements.forEach(el => {
        el.style.animationPlayState = 'paused';
        observer.observe(el);
    });
});

// Initialize molecular background
let molecularBg;
document.addEventListener('DOMContentLoaded', () => {
    molecularBg = new MolecularBackground();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (molecularBg) {
        molecularBg.destroy();
    }
});

// Dynamic Text Effect for Hero Title
class TypingEffect {
    constructor(element, texts, speed = 100) {
        this.element = element;
        this.texts = texts;
        this.speed = speed;
        this.textIndex = 0;
        this.charIndex = 0;
        this.isDeleting = false;
        this.currentText = '';
        
        this.type();
    }
    
    type() {
        const fullText = this.texts[this.textIndex];
        
        if (this.isDeleting) {
            this.currentText = fullText.substring(0, this.charIndex - 1);
            this.charIndex--;
        } else {
            this.currentText = fullText.substring(0, this.charIndex + 1);
            this.charIndex++;
        }
        
        this.element.textContent = this.currentText;
        
        let typeSpeed = this.speed;
        if (this.isDeleting) typeSpeed /= 2;
        
        if (!this.isDeleting && this.charIndex === fullText.length) {
            typeSpeed = 2000;
            this.isDeleting = true;
        } else if (this.isDeleting && this.charIndex === 0) {
            this.isDeleting = false;
            this.textIndex = (this.textIndex + 1) % this.texts.length;
            typeSpeed = 500;
        }
        
        setTimeout(() => this.type(), typeSpeed);
    }
}

// Performance optimization: Throttle scroll events
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}

// Apply throttling to scroll event
window.addEventListener('scroll', throttle(() => {
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 100) {
        navbar.style.background = 'rgba(255, 255, 255, 0.98)';
        navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
    } else {
        navbar.style.background = 'rgba(255, 255, 255, 0.95)';
        navbar.style.boxShadow = 'none';
    }
}, 16));

// Add particle trail effect on mouse move
let particles = [];

function createParticle(x, y) {
    return {
        x: x,
        y: y,
        size: Math.random() * 3 + 1,
        speedX: (Math.random() - 0.5) * 2,
        speedY: (Math.random() - 0.5) * 2,
        color: `hsl(${Math.random() * 60 + 240}, 70%, 60%)`,
        life: 1,
        decay: Math.random() * 0.02 + 0.01
    };
}

function updateParticles() {
    particles = particles.filter(particle => {
        particle.x += particle.speedX;
        particle.y += particle.speedY;
        particle.life -= particle.decay;
        particle.size *= 0.99;
        
        return particle.life > 0 && particle.size > 0.1;
    });
}

document.addEventListener('mousemove', (e) => {
    if (Math.random() < 0.1) { // Only create particles occasionally
        particles.push(createParticle(e.clientX, e.clientY));
    }
});

// Animate particles on the molecular canvas
function animateParticles() {
    if (molecularBg && molecularBg.ctx && particles.length > 0) {
        particles.forEach(particle => {
            molecularBg.ctx.save();
            molecularBg.ctx.globalAlpha = particle.life;
            molecularBg.ctx.fillStyle = particle.color;
            molecularBg.ctx.beginPath();
            molecularBg.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            molecularBg.ctx.fill();
            molecularBg.ctx.restore();
        });
    }
    
    updateParticles();
    requestAnimationFrame(animateParticles);
}

// Start particle animation
document.addEventListener('DOMContentLoaded', () => {
    animateParticles();
});
