// mRNA Translation Animation
class TranslationAnimation {
    constructor() {
        this.canvas = document.getElementById('translationCanvas');
        if (!this.canvas) return;
        
        this.ctx = this.canvas.getContext('2d');
        this.setupCanvas();
        
        // Animation state
        this.time = 0;
        this.animationProgress = 0;
        this.isVisible = false;
        
        // mRNA sequence (simplified codons)
        this.mRNA = [
            'AUG', 'UUC', 'GAA', 'CUG', 'AAG', 'GCA', 'UUA', 'GGU', 
            'CAC', 'GUC', 'AUC', 'UGG', 'CCU', 'UAG'
        ];
        
        // Amino acids corresponding to codons
        this.aminoAcids = [
            'Met', 'Phe', 'Glu', 'Leu', 'Lys', 'Ala', 'Leu', 'Gly',
            'His', 'Val', 'Ile', 'Trp', 'Pro', 'Stop'
        ];
        
        // Animation components
        this.ribosome = {
            x: this.canvas.width * 0.3,
            y: this.canvas.height * 0.5,
            width: 120,
            height: 80
        };
        
        this.mRNAPosition = 0;
        this.proteinChain = [];
        this.currentCodon = 0;
        this.tRNAs = [];
        
        this.setupScrollObserver();
        this.animate();
    }
    
    setupCanvas() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * window.devicePixelRatio;
        this.canvas.height = rect.height * window.devicePixelRatio;
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
    }
    
    setupScrollObserver() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                this.isVisible = entry.isIntersecting;
                if (this.isVisible) {
                    this.startTranslation();
                }
            });
        }, { threshold: 0.3 });
        
        observer.observe(this.canvas);
    }
    
    startTranslation() {
        this.animationProgress = 0;
        this.currentCodon = 0;
        this.proteinChain = [];
        this.tRNAs = [];
        this.mRNAPosition = 0;
    }
    
    drawmRNA() {
        const startX = 50;
        const y = this.canvas.height * 0.7;
        const codonWidth = 40;
        const codonHeight = 25;
        
        // Draw mRNA backbone
        this.ctx.strokeStyle = '#3b82f6';
        this.ctx.lineWidth = 4;
        this.ctx.beginPath();
        this.ctx.moveTo(startX, y);
        this.ctx.lineTo(startX + this.mRNA.length * codonWidth + 50, y);
        this.ctx.stroke();
        
        // Draw codons
        this.mRNA.forEach((codon, index) => {
            const x = startX + index * codonWidth + this.mRNAPosition;
            const isCurrentCodon = index === this.currentCodon;
            
            // Codon background
            this.ctx.fillStyle = isCurrentCodon ? '#fbbf24' : '#1e40af';
            this.ctx.fillRect(x, y - codonHeight/2, codonWidth - 5, codonHeight);
            
            // Codon text
            this.ctx.fillStyle = 'white';
            this.ctx.font = 'bold 10px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(codon, x + codonWidth/2 - 2.5, y + 3);
            
            // Draw nucleotides as small circles
            for (let i = 0; i < 3; i++) {
                const nucleotideX = x + (i + 0.5) * (codonWidth - 5) / 3;
                this.ctx.fillStyle = this.getNucleotideColor(codon[i]);
                this.ctx.beginPath();
                this.ctx.arc(nucleotideX, y - codonHeight/2 - 10, 4, 0, Math.PI * 2);
                this.ctx.fill();
            }
        });
    }
    
    getNucleotideColor(nucleotide) {
        const colors = {
            'A': '#ef4444', // red
            'U': '#22c55e', // green
            'G': '#8b5cf6', // purple
            'C': '#f59e0b'  // orange
        };
        return colors[nucleotide] || '#6b7280';
    }
    
    drawRibosome() {
        const { x, y, width, height } = this.ribosome;
        
        // Large subunit (60S)
        const gradient1 = this.ctx.createRadialGradient(x, y - 20, 0, x, y - 20, width/2);
        gradient1.addColorStop(0, '#a855f7');
        gradient1.addColorStop(1, '#7c3aed');
        
        this.ctx.fillStyle = gradient1;
        this.ctx.beginPath();
        this.ctx.ellipse(x, y - 20, width/2, height/3, 0, 0, Math.PI * 2);
        this.ctx.fill();
        
        // Small subunit (40S)
        const gradient2 = this.ctx.createRadialGradient(x, y + 20, 0, x, y + 20, width/2.5);
        gradient2.addColorStop(0, '#ec4899');
        gradient2.addColorStop(1, '#db2777');
        
        this.ctx.fillStyle = gradient2;
        this.ctx.beginPath();
        this.ctx.ellipse(x, y + 20, width/2.5, height/3.5, 0, 0, Math.PI * 2);
        this.ctx.fill();
        
        // Binding sites
        this.ctx.fillStyle = '#1f2937';
        this.ctx.beginPath();
        this.ctx.arc(x - 25, y, 8, 0, Math.PI * 2); // A site
        this.ctx.fill();
        
        this.ctx.beginPath();
        this.ctx.arc(x, y, 8, 0, Math.PI * 2); // P site
        this.ctx.fill();
        
        this.ctx.beginPath();
        this.ctx.arc(x + 25, y, 8, 0, Math.PI * 2); // E site
        this.ctx.fill();
        
        // Labels
        this.ctx.fillStyle = 'white';
        this.ctx.font = 'bold 8px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('A', x - 25, y + 3);
        this.ctx.fillText('P', x, y + 3);
        this.ctx.fillText('E', x + 25, y + 3);
        
        // Tunnel for nascent protein
        this.ctx.strokeStyle = '#374151';
        this.ctx.lineWidth = 3;
        this.ctx.beginPath();
        this.ctx.arc(x + 40, y - 15, 6, 0, Math.PI * 2);
        this.ctx.stroke();
    }
    
    drawtRNAs() {
        this.tRNAs.forEach((tRNA, index) => {
            const { x, y, aminoAcid, isActive } = tRNA;
            
            // tRNA body
            this.ctx.fillStyle = isActive ? '#10b981' : '#6b7280';
            this.ctx.beginPath();
            this.ctx.moveTo(x, y - 20);
            this.ctx.lineTo(x - 10, y);
            this.ctx.lineTo(x + 10, y);
            this.ctx.closePath();
            this.ctx.fill();
            
            // Amino acid
            if (aminoAcid !== 'Stop') {
                this.ctx.fillStyle = '#fbbf24';
                this.ctx.beginPath();
                this.ctx.arc(x, y - 25, 6, 0, Math.PI * 2);
                this.ctx.fill();
                
                // Amino acid label
                this.ctx.fillStyle = 'black';
                this.ctx.font = 'bold 8px Arial';
                this.ctx.textAlign = 'center';
                this.ctx.fillText(aminoAcid, x, y - 22);
            }
            
            // Anticodon
            this.ctx.fillStyle = 'white';
            this.ctx.font = '8px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText('tRNA', x, y + 5);
        });
    }
    
    drawProteinChain() {
        if (this.proteinChain.length === 0) return;
        
        const startX = this.ribosome.x + 60;
        const startY = this.ribosome.y - 30;
        
        // Protein backbone
        this.ctx.strokeStyle = '#dc2626';
        this.ctx.lineWidth = 3;
        this.ctx.beginPath();
        this.ctx.moveTo(startX, startY);
        
        this.proteinChain.forEach((aminoAcid, index) => {
            const x = startX + (index + 1) * 20;
            const y = startY + Math.sin(index * 0.5) * 10;
            this.ctx.lineTo(x, y);
        });
        this.ctx.stroke();
        
        // Amino acid residues
        this.proteinChain.forEach((aminoAcid, index) => {
            const x = startX + (index + 1) * 20;
            const y = startY + Math.sin(index * 0.5) * 10;
            
            // Amino acid circle
            this.ctx.fillStyle = this.getAminoAcidColor(aminoAcid);
            this.ctx.beginPath();
            this.ctx.arc(x, y, 8, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Amino acid label
            this.ctx.fillStyle = 'white';
            this.ctx.font = 'bold 6px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(aminoAcid.substring(0, 3), x, y + 2);
        });
        
        // "Newly Formed Protein" label with arrow
        if (this.proteinChain.length > 2) {
            const lastX = startX + this.proteinChain.length * 20;
            const lastY = startY + Math.sin((this.proteinChain.length - 1) * 0.5) * 10;
            
            // Arrow
            this.ctx.strokeStyle = '#374151';
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            this.ctx.moveTo(lastX + 15, lastY - 20);
            this.ctx.lineTo(lastX + 5, lastY - 5);
            this.ctx.stroke();
            
            // Arrowhead
            this.ctx.beginPath();
            this.ctx.moveTo(lastX + 5, lastY - 5);
            this.ctx.lineTo(lastX + 2, lastY - 10);
            this.ctx.moveTo(lastX + 5, lastY - 5);
            this.ctx.lineTo(lastX + 10, lastY - 8);
            this.ctx.stroke();
            
            // Label
            this.ctx.fillStyle = '#374151';
            this.ctx.font = 'bold 10px Arial';
            this.ctx.textAlign = 'left';
            this.ctx.fillText('Newly Formed', lastX + 20, lastY - 25);
            this.ctx.fillText('Protein', lastX + 20, lastY - 15);
        }
    }
    
    getAminoAcidColor(aminoAcid) {
        const colors = {
            'Met': '#8b5cf6', 'Phe': '#3b82f6', 'Glu': '#ef4444', 'Leu': '#10b981',
            'Lys': '#f59e0b', 'Ala': '#6366f1', 'Gly': '#ec4899', 'His': '#14b8a6',
            'Val': '#f97316', 'Ile': '#84cc16', 'Trp': '#a855f7', 'Pro': '#06b6d4'
        };
        return colors[aminoAcid] || '#6b7280';
    }
    
    updateAnimation() {
        if (!this.isVisible) return;
        
        this.time += 0.02;
        this.animationProgress += 0.005;
        
        // Update current codon based on animation progress
        const targetCodon = Math.floor(this.animationProgress * this.mRNA.length);
        if (targetCodon < this.mRNA.length && targetCodon !== this.currentCodon) {
            this.currentCodon = targetCodon;
            
            // Add new tRNA
            if (this.currentCodon < this.aminoAcids.length) {
                this.tRNAs.push({
                    x: this.ribosome.x - 25,
                    y: this.ribosome.y,
                    aminoAcid: this.aminoAcids[this.currentCodon],
                    isActive: true
                });
                
                // Add amino acid to growing protein chain
                if (this.aminoAcids[this.currentCodon] !== 'Stop') {
                    this.proteinChain.push(this.aminoAcids[this.currentCodon]);
                }
            }
            
            // Deactivate old tRNAs
            this.tRNAs.forEach((tRNA, index) => {
                if (index < this.tRNAs.length - 1) {
                    tRNA.isActive = false;
                    tRNA.x += 25; // Move to E site then away
                }
            });
            
            // Remove old tRNAs
            this.tRNAs = this.tRNAs.filter(tRNA => tRNA.x < this.ribosome.x + 100);
        }
        
        // Move mRNA
        this.mRNAPosition = -this.currentCodon * 15;
        
        // Reset animation when complete
        if (this.animationProgress >= 1) {
            setTimeout(() => {
                this.startTranslation();
            }, 2000);
        }
    }
    
    drawLabels() {
        // Title
        this.ctx.fillStyle = '#1f2937';
        this.ctx.font = 'bold 16px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('Protein Translation', this.canvas.width / 2, 30);
        
        // mRNA label
        this.ctx.fillStyle = '#3b82f6';
        this.ctx.font = 'bold 12px Arial';
        this.ctx.textAlign = 'left';
        this.ctx.fillText('mRNA', 20, this.canvas.height * 0.7 - 30);
        
        // Ribosome label
        this.ctx.fillStyle = '#7c3aed';
        this.ctx.font = 'bold 12px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('Ribosome', this.ribosome.x, this.ribosome.y + 60);
        
        // Progress indicator
        const progress = Math.min(this.animationProgress, 1);
        const progressWidth = 200;
        const progressX = (this.canvas.width - progressWidth) / 2;
        const progressY = this.canvas.height - 30;
        
        // Progress bar background
        this.ctx.fillStyle = '#e5e7eb';
        this.ctx.fillRect(progressX, progressY, progressWidth, 6);
        
        // Progress bar fill
        this.ctx.fillStyle = '#3b82f6';
        this.ctx.fillRect(progressX, progressY, progressWidth * progress, 6);
        
        // Progress text
        this.ctx.fillStyle = '#374151';
        this.ctx.font = '10px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(`Translation Progress: ${Math.round(progress * 100)}%`, this.canvas.width / 2, progressY - 8);
    }
    
    draw() {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw components
        this.drawmRNA();
        this.drawRibosome();
        this.drawtRNAs();
        this.drawProteinChain();
        this.drawLabels();
    }
    
    animate() {
        this.updateAnimation();
        this.draw();
        requestAnimationFrame(() => this.animate());
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new TranslationAnimation();
    
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
