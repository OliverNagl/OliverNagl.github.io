document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('protein-container');
    const canvas = document.getElementById('proteinCanvas');

    if (!container || !canvas) {
        return;
    }

    // Scene Setup
    const scene = new THREE.Scene();

    // Camera Setup
    const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 2000);
    camera.position.z = 700; // Adjusted for larger protein structure

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

                if (unravelFactor > 0.01 || true) { // Always update for vibe
                    for (let i = 0; i < particleCount; i++) {
                        const ix = i * 3;
                        const iy = i * 3 + 1;
                        const iz = i * 3 + 2;

                        const ox = originalPositions[ix];
                        const oy = originalPositions[iy];
                        const oz = originalPositions[iz];

                        const vibeX = Math.sin(time + ox * 0.05) * 0.2;
                        const vibeY = Math.cos(time + oy * 0.05) * 0.2;
                        const vibeZ = Math.sin(time + oz * 0.05) * 0.2;

                        // Explosion
                        const dx = ox - center.x;
                        const dy = oy - center.y;
                        const dz = oz - center.z;

                        // Optimization: Calculate distSq first
                        const distSq = dx * dx + dy * dy + dz * dz;
                        const dist = Math.sqrt(distSq);

                        // Avoid divide by zero
                        const scale = (dist > 0.001) ? (1.0 / dist) : 0;

                        const dirX = dx * scale;
                        const dirY = dy * scale;
                        const dirZ = dz * scale;

                        const explosionStrength = unravelFactor * 300;
                        const noiseStrength = unravelFactor * 5;

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
