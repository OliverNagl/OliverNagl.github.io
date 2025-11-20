document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('protein-container');
    const canvas = document.getElementById('proteinCanvas');

    if (!container || !canvas) {
        return;
    }

    // Scene Setup
    const scene = new THREE.Scene();

    // Camera Setup
    const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.z = 120;

    // Renderer Setup
    const renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        alpha: true,
        antialias: true
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Load Protein Data
    fetch('protein_coords.bin')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.arrayBuffer();
        })
        .then(data => {
            const positions = new Float32Array(data);
            const particleCount = positions.length / 3;
            
            console.log(`Loaded ${particleCount} particles`);

            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            
            // Create a copy for animation reference
            const originalPositions = new Float32Array(positions);
            
            // Colors
            const colors = new Float32Array(particleCount * 3);
            const color1 = new THREE.Color('#4ECDC4');
            const color2 = new THREE.Color('#26A69A');

            for (let i = 0; i < particleCount; i++) {
                const mixedColor = color1.clone().lerp(color2, Math.random());
                colors[i * 3] = mixedColor.r;
                colors[i * 3 + 1] = mixedColor.g;
                colors[i * 3 + 2] = mixedColor.b;
            }
            geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

            const material = new THREE.PointsMaterial({
                size: 0.3,
                vertexColors: true,
                transparent: true,
                opacity: 0.8,
                blending: THREE.AdditiveBlending
            });

            const particles = new THREE.Points(geometry, material);
            
            // Center the protein
            geometry.computeBoundingBox();
            const center = new THREE.Vector3();
            geometry.boundingBox.getCenter(center);
            particles.position.sub(center);
            
            scene.add(particles);

            // Animation Variables
            let time = 0;
            let scrollY = 0;

            // Scroll Listener
            window.addEventListener('scroll', () => {
                scrollY = window.scrollY;
            });

            // Resize Listener
            window.addEventListener('resize', () => {
                camera.aspect = container.clientWidth / container.clientHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(container.clientWidth, container.clientHeight);
            });

            // Animation Loop
            function animate() {
                requestAnimationFrame(animate);
                time += 0.005;

                // Vibing (Rotation + slight pulse)
                particles.rotation.y = time * 0.05;
                particles.rotation.z = time * 0.02;

                const currentPositions = particles.geometry.attributes.position.array;

                // Unraveling factor based on scroll
                const unravelFactor = Math.min(Math.max(scrollY / window.innerHeight, 0), 2.0);

                // Optimization: Only update if necessary (e.g. scroll changed or time passed)
                // For "vibing", we need to update every frame.
                
                // To optimize 400k particles, we might want to do this in a vertex shader instead of CPU.
                // But for now, let's try CPU. If it's laggy, we can move to shader material.
                // CPU loop for 444k particles * 3 ops might be slow (1.3M ops per frame).
                // Let's try to keep it simple.
                
                if (unravelFactor > 0.01 || true) { // Always update for vibe
                     for (let i = 0; i < particleCount; i++) {
                        const ix = i * 3;
                        const iy = i * 3 + 1;
                        const iz = i * 3 + 2;

                        const ox = originalPositions[ix];
                        const oy = originalPositions[iy];
                        const oz = originalPositions[iz];

                        // Vibing noise - simplified for performance
                        // Math.sin is expensive. Precompute or use simple approximation?
                        // Let's reduce frequency of sin calls or use a lookup if needed.
                        // For now, standard implementation.
                        
                        const vibeX = Math.sin(time + ox * 0.05) * 0.2;
                        const vibeY = Math.cos(time + oy * 0.05) * 0.2;
                        const vibeZ = Math.sin(time + oz * 0.05) * 0.2;

                        // Explosion
                        const dx = ox - center.x;
                        const dy = oy - center.y;
                        const dz = oz - center.z;
                        
                        // Fast distance approximation or just use raw vector?
                        // We need direction.
                        // Let's approximate direction as just the offset from center (unnormalized) * factor
                        // to save Sqrt calls? No, that would distort shape.
                        // We'll stick to correct math for now.
                        
                        // Optimization: Calculate distSq first
                        const distSq = dx*dx + dy*dy + dz*dz;
                        const dist = Math.sqrt(distSq);
                        
                        // Avoid divide by zero
                        const scale = (dist > 0.001) ? (1.0 / dist) : 0;
                        
                        const dirX = dx * scale;
                        const dirY = dy * scale;
                        const dirZ = dz * scale;

                        const explosionStrength = unravelFactor * 50; 
                        const noiseStrength = unravelFactor * 5;
                        
                        // Simple random noise is deterministic per frame if we don't change seed, 
                        // but Math.random() changes every call. 
                        // We want the noise to be stable or animating smoothly?
                        // "Thousands of dots" usually implies some jitter.
                        // If we use Math.random() every frame, it will look like TV static.
                        // We probably want "stable" noise or slowly moving noise.
                        // Let's use the vibe as the noise and just expand.
                        
                        currentPositions[ix] = ox + vibeX + (dirX * explosionStrength);
                        currentPositions[iy] = oy + vibeY + (dirY * explosionStrength);
                        currentPositions[iz] = oz + vibeZ + (dirZ * explosionStrength);
                    }
                    particles.geometry.attributes.position.needsUpdate = true;
                }
                
                renderer.render(scene, camera);
            }

            animate();
        })
        .catch(error => console.error('Error loading protein data:', error));
});
