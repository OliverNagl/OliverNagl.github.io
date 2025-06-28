// Interdisciplinary Network Animation
class NetworkAnimation {
    constructor() {
        console.log('Initializing NetworkAnimation...');
        this.canvas = document.getElementById('translationCanvas');
        if (!this.canvas) {
            console.error('Canvas not found!');
            return;
        }
        console.log('Canvas found:', this.canvas);
        
        this.ctx = this.canvas.getContext('2d');
        this.setupCanvas();
        
        // Network parameters
        this.nodes = [];
        this.connections = [];
        this.time = 0;
        this.scrollPosition = 0;
        this.isVisible = false;
        
        // Disciplines with colors and positions
        this.disciplines = [
            { name: 'Biotechnology', color: '#8b5cf6', x: 0.2, y: 0.3 },
            { name: 'Computer Science', color: '#3b82f6', x: 0.8, y: 0.2 },
            { name: 'Chemical Engineering', color: '#ef4444', x: 0.7, y: 0.7 },
            { name: 'Bioinformatics', color: '#10b981', x: 0.3, y: 0.8 },
            { name: 'Machine Learning', color: '#f59e0b', x: 0.5, y: 0.15 },
            { name: 'Molecular Dynamics', color: '#ec4899', x: 0.1, y: 0.6 },
            { name: 'Data Science', color: '#06b6d4', x: 0.85, y: 0.5 },
            { name: 'Wet Lab', color: '#84cc16', x: 0.4, y: 0.5 }
        ];
        
        this.createNetwork();
        this.setupScrollObserver();
        this.animate();
    }
    
    setupCanvas() {
        this.canvas.width = 500;
        this.canvas.height = 400;
        this.canvas.style.width = '500px';
        this.canvas.style.height = '400px';
    }
    
    createNetwork() {
        // Create nodes for each discipline
        this.nodes = this.disciplines.map((discipline, index) => ({
            id: index,
            name: discipline.name,
            x: discipline.x * this.canvas.width,
            y: discipline.y * this.canvas.height,
            originalX: discipline.x * this.canvas.width,
            originalY: discipline.y * this.canvas.height,
            color: discipline.color,
            radius: 20 + Math.random() * 15,
            pulse: Math.random() * Math.PI * 2,
            velocity: { x: 0, y: 0 },
            connections: []
        }));
        
        // Create connections between nodes with varying strengths
        this.connections = [];
        for (let i = 0; i < this.nodes.length; i++) {
            for (let j = i + 1; j < this.nodes.length; j++) {
                const distance = this.getDistance(this.nodes[i], this.nodes[j]);
                const maxDistance = Math.sqrt(this.canvas.width * this.canvas.width + this.canvas.height * this.canvas.height);
                
                // Connection strength based on distance and conceptual similarity
                let strength = 1 - (distance / maxDistance);
                
                // Add conceptual connections (stronger between related fields)
                const conceptualStrength = this.getConceptualStrength(this.nodes[i].name, this.nodes[j].name);
                strength = Math.max(strength * 0.3, conceptualStrength);
                
                if (strength > 0.2) {
                    this.connections.push({
                        nodeA: i,
                        nodeB: j,
                        strength: strength,
                        thickness: strength * 3,
                        alpha: strength * 0.8,
                        oscillation: Math.random() * Math.PI * 2
                    });
                    
                    this.nodes[i].connections.push(j);
                    this.nodes[j].connections.push(i);
                }
            }
        }
    }
    
    getConceptualStrength(nameA, nameB) {
        const strongConnections = {
            'Biotechnology': ['Bioinformatics', 'Molecular Dynamics', 'Wet Lab'],
            'Computer Science': ['Machine Learning', 'Data Science', 'Bioinformatics'],
            'Chemical Engineering': ['Molecular Dynamics', 'Biotechnology'],
            'Machine Learning': ['Data Science', 'Bioinformatics'],
            'Bioinformatics': ['Data Science', 'Machine Learning', 'Molecular Dynamics']
        };
        
        if (strongConnections[nameA] && strongConnections[nameA].includes(nameB)) {
            return 0.8 + Math.random() * 0.2;
        }
        if (strongConnections[nameB] && strongConnections[nameB].includes(nameA)) {
            return 0.8 + Math.random() * 0.2;
        }
        
        return Math.random() * 0.4;
    }
    
    getDistance(nodeA, nodeB) {
        return Math.sqrt(Math.pow(nodeA.x - nodeB.x, 2) + Math.pow(nodeA.y - nodeB.y, 2));
    }
    
    setupScrollObserver() {
        this.isVisible = true;
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                this.isVisible = entry.isIntersecting;
            });
        }, { threshold: 0.3 });
        
        observer.observe(this.canvas);
        
        // Listen for scroll events to create thrumming effect
        window.addEventListener('scroll', (e) => {
            this.scrollPosition = window.scrollY;
        });
    }
    
    updateNetwork() {
        if (!this.isVisible) return;
        
        this.time += 0.02;
        
        // Calculate scroll influence (thrumming effect)
        const scrollInfluence = Math.sin(this.scrollPosition * 0.01) * 0.5 + 0.5;
        const thrumIntensity = scrollInfluence * 2;
        
        // Update nodes
        this.nodes.forEach((node, index) => {
            // Gentle floating motion
            const baseFloat = Math.sin(this.time + index) * 2;
            const scrollFloat = Math.cos(this.time * 2 + index + this.scrollPosition * 0.01) * thrumIntensity;
            
            node.x = node.originalX + baseFloat + scrollFloat;
            node.y = node.originalY + Math.cos(this.time * 0.7 + index) * 1.5 + scrollFloat * 0.5;
            
            // Update pulse for breathing effect
            node.pulse += 0.03 + scrollInfluence * 0.02;
        });
        
        // Update connections
        this.connections.forEach(connection => {
            connection.oscillation += 0.05 + scrollInfluence * 0.1;
        });
    }
    
    drawConnections() {
        this.connections.forEach(connection => {
            const nodeA = this.nodes[connection.nodeA];
            const nodeB = this.nodes[connection.nodeB];
            
            // Dynamic thickness and alpha based on oscillation and scroll
            const oscillation = Math.sin(connection.oscillation) * 0.3 + 0.7;
            const thickness = connection.thickness * oscillation;
            const alpha = connection.alpha * oscillation;
            
            // Create gradient line
            const gradient = this.ctx.createLinearGradient(nodeA.x, nodeA.y, nodeB.x, nodeB.y);
            gradient.addColorStop(0, nodeA.color + Math.floor(alpha * 255).toString(16).padStart(2, '0'));
            gradient.addColorStop(1, nodeB.color + Math.floor(alpha * 255).toString(16).padStart(2, '0'));
            
            this.ctx.strokeStyle = gradient;
            this.ctx.lineWidth = thickness;
            this.ctx.beginPath();
            this.ctx.moveTo(nodeA.x, nodeA.y);
            this.ctx.lineTo(nodeB.x, nodeB.y);
            this.ctx.stroke();
            
            // Add flowing particles along strong connections
            if (connection.strength > 0.6) {
                const t = (Math.sin(this.time * 2 + connection.oscillation) + 1) / 2;
                const particleX = nodeA.x + (nodeB.x - nodeA.x) * t;
                const particleY = nodeA.y + (nodeB.y - nodeA.y) * t;
                
                this.ctx.fillStyle = '#ffffff80';
                this.ctx.beginPath();
                this.ctx.arc(particleX, particleY, 2, 0, Math.PI * 2);
                this.ctx.fill();
            }
        });
    }
    
    drawNodes() {
        this.nodes.forEach(node => {
            // Breathing radius based on pulse and scroll
            const pulseRadius = Math.sin(node.pulse) * 3;
            const currentRadius = node.radius + pulseRadius;
            
            // Outer glow
            const glowGradient = this.ctx.createRadialGradient(
                node.x, node.y, 0,
                node.x, node.y, currentRadius * 2
            );
            glowGradient.addColorStop(0, node.color + '80');
            glowGradient.addColorStop(0.5, node.color + '40');
            glowGradient.addColorStop(1, node.color + '00');
            
            this.ctx.fillStyle = glowGradient;
            this.ctx.beginPath();
            this.ctx.arc(node.x, node.y, currentRadius * 1.5, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Main node
            const nodeGradient = this.ctx.createRadialGradient(
                node.x - currentRadius * 0.3, node.y - currentRadius * 0.3, 0,
                node.x, node.y, currentRadius
            );
            nodeGradient.addColorStop(0, this.lightenColor(node.color, 0.3));
            nodeGradient.addColorStop(1, node.color);
            
            this.ctx.fillStyle = nodeGradient;
            this.ctx.beginPath();
            this.ctx.arc(node.x, node.y, currentRadius, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Highlight
            this.ctx.fillStyle = '#ffffff60';
            this.ctx.beginPath();
            this.ctx.arc(node.x - currentRadius * 0.3, node.y - currentRadius * 0.3, currentRadius * 0.3, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Label
            this.ctx.fillStyle = '#ffffff';
            this.ctx.font = 'bold 8px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(node.name, node.x, node.y + currentRadius + 15);
        });
    }
    
    lightenColor(color, amount) {
        // Simple color lightening
        const num = parseInt(color.replace("#", ""), 16);
        const amt = Math.round(2.55 * amount * 100);
        const R = (num >> 16) + amt;
        const G = (num >> 8 & 0x00FF) + amt;
        const B = (num & 0x0000FF) + amt;
        return "#" + (0x1000000 + (R < 255 ? R < 1 ? 0 : R : 255) * 0x10000 +
            (G < 255 ? G < 1 ? 0 : G : 255) * 0x100 +
            (B < 255 ? B < 1 ? 0 : B : 255)).toString(16).slice(1);
    }
    
    drawLabels() {
        // Title
        this.ctx.fillStyle = '#ffffff';
        this.ctx.font = 'bold 18px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('Interdisciplinary Network', this.canvas.width / 2, 30);
        
        // Subtitle
        this.ctx.fillStyle = '#cccccc';
        this.ctx.font = '12px Arial';
        this.ctx.fillText('Scroll to see network thrumming', this.canvas.width / 2, 50);
        
        // Connection strength legend
        this.ctx.fillStyle = '#aaaaaa';
        this.ctx.font = '10px Arial';
        this.ctx.textAlign = 'left';
        this.ctx.fillText('Line thickness = Connection strength', 20, this.canvas.height - 20);
    }
    
    draw() {
        // Clear with dark background
        this.ctx.fillStyle = '#0f172a';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw network
        this.drawConnections();
        this.drawNodes();
        this.drawLabels();
    }
    
    animate() {
        this.updateNetwork();
        this.draw();
        requestAnimationFrame(() => this.animate());
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new NetworkAnimation();
    
    // Smooth scrolling for navigation links
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
    
    // Mobile navigation toggle
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');
    
    if (hamburger && navMenu) {
        hamburger.addEventListener('click', () => {
            hamburger.classList.toggle('active');
            navMenu.classList.toggle('active');
        });
        
        // Close mobile menu when clicking on a link
        document.querySelectorAll('.nav-link').forEach(n => n.addEventListener('click', () => {
            hamburger.classList.remove('active');
            navMenu.classList.remove('active');
        }));
    }
    
    // Navbar scroll effect
    window.addEventListener('scroll', () => {
        const navbar = document.querySelector('.navbar');
        if (window.scrollY > 50) {
            navbar.style.background = 'rgba(255, 255, 255, 0.98)';
            navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
        } else {
            navbar.style.background = 'rgba(255, 255, 255, 0.95)';
            navbar.style.boxShadow = 'none';
        }
    });
});
