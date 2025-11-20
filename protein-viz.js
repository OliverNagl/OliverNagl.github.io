document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('protein-container');
    const canvas = document.getElementById('proteinCanvas');

    if (!container || !canvas) {
        return;
    }

    // Scene Setup
    const scene = new THREE.Scene();

    // Camera Setup
    const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 3000);
    camera.position.z = 470;

    // Renderer Setup
    const renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        alpha: true,
        antialias: true
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Shader Material
    const particleMaterial = new THREE.ShaderMaterial({
        uniforms: {
            pixelRatio: { value: renderer.getPixelRatio() },
            color1: { value: new THREE.Color('#4ECDC4') },
            color2: { value: new THREE.Color('#26A69A') },
            transitionProgress: { value: 0.0 },
            scrollProgress: { value: 0.0 },
            time: { value: 0.0 }
        },
        vertexShader: `
            attribute float alpha;
            attribute float colorMix;
            attribute vec3 targetPosition;
            attribute float targetAlpha;
            attribute vec3 randomDir;
            
            varying float vAlpha;
            varying float vColorMix;
            
            uniform float transitionProgress;
            uniform float scrollProgress;
            uniform float time;

            void main() {
                // Interpolate position and alpha
                vec3 currentPos = mix(position, targetPosition, transitionProgress);
                vAlpha = mix(alpha, targetAlpha, transitionProgress);
                
                // Scroll explosion effect
                vec3 explosion = randomDir * scrollProgress * 300.0;
                
                // Vibe check - REDUCED to prevent flickering
                // Very slow, very subtle movement just to keep it "alive" but not jittery
                float vibe = sin(time * 0.5 + currentPos.x * 0.01) * 0.5;
                
                currentPos += explosion;
                // currentPos.y += vibe;

                vColorMix = colorMix;
                
                vec4 mvPosition = modelViewMatrix * vec4(currentPos, 1.0);
                gl_PointSize = 2.0 * (300.0 / -mvPosition.z); // Size attenuation
                gl_Position = projectionMatrix * mvPosition;
            }
        `,
        fragmentShader: `
            uniform vec3 color1;
            uniform vec3 color2;
            varying float vAlpha;
            varying float vColorMix;

            void main() {
                if (vAlpha < 0.01) discard;
                vec3 color = mix(color1, color2, vColorMix);
                
                // Circular particle
                vec2 coord = gl_PointCoord - vec2(0.5);
                if(length(coord) > 0.5) discard;

                gl_FragColor = vec4(color, vAlpha);
            }
        `,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending
    });

    // State
    let proteins = [];
    let currentProteinIndex = 0;
    let nextProteinIndex = 0;
    let particles;
    let geometry;

    // Animation State
    const HOLD_DURATION = 10000; // 10 seconds
    const TRANSITION_DURATION = 5000; // 5 seconds
    let lastStateChangeTime = performance.now();
    let state = 'HOLD'; // 'HOLD' or 'TRANSITION'
    let isPaused = false;

    // Mouse Interaction
    let mouseX = 0;
    let mouseY = 0;
    document.addEventListener('mousemove', (event) => {
        mouseX = (event.clientX / window.innerWidth) * 2 - 1;
        mouseY = -(event.clientY / window.innerHeight) * 2 + 1;
    });

    // Zoom Interaction
    container.addEventListener('wheel', (event) => {
        event.preventDefault(); // Prevent page scroll while zooming

        const zoomSpeed = 0.5;
        camera.position.z += event.deltaY * zoomSpeed;

        // Clamp zoom
        camera.position.z = Math.max(120, Math.min(1000, camera.position.z));
    }, { passive: false });

    // Scroll Interaction
    let scrollY = 0;
    window.addEventListener('scroll', () => {
        scrollY = window.scrollY;
        const maxScroll = window.innerHeight;
        const progress = Math.min(Math.max(scrollY / maxScroll, 0), 1);
        particleMaterial.uniforms.scrollProgress.value = progress;

        // Pause morphing when scrolling/exploded
        isPaused = progress > 0.05;
    });

    // Resize Listener
    window.addEventListener('resize', () => {
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
        particleMaterial.uniforms.pixelRatio.value = renderer.getPixelRatio();
    });

    // Load Data
    async function loadProteins() {
        try {
            const manifestRes = await fetch('Protein_coords/protein_manifest.json');
            const manifest = await manifestRes.json();

            for (const item of manifest) {
                const res = await fetch(`Protein_coords/${item.file}`);
                const buffer = await res.arrayBuffer();
                const positions = new Float32Array(buffer);

                // Subsample: Increase step to reduce points (User request)
                const step = 4;
                const count = Math.floor(positions.length / 3 / step);
                const subsampled = new Float32Array(count * 3);

                for (let i = 0; i < count; i++) {
                    subsampled[i * 3] = positions[i * step * 3];
                    subsampled[i * 3 + 1] = positions[i * step * 3 + 1];
                    subsampled[i * 3 + 2] = positions[i * step * 3 + 2];
                }

                proteins.push({
                    name: item.name,
                    positions: subsampled,
                    count: count
                });
            }

            initVisualization();

        } catch (error) {
            console.error("Error loading proteins:", error);
        }
    }

    function initVisualization() {
        if (proteins.length === 0) return;

        // Random Initialization
        currentProteinIndex = Math.floor(Math.random() * proteins.length);
        nextProteinIndex = (currentProteinIndex + 1) % proteins.length;

        // Find max particle count to allocate buffers
        let maxCount = 0;
        proteins.forEach(p => maxCount = Math.max(maxCount, p.count));

        geometry = new THREE.BufferGeometry();

        // Attributes
        const positions = new Float32Array(maxCount * 3);
        const targetPositions = new Float32Array(maxCount * 3);
        const alphas = new Float32Array(maxCount);
        const targetAlphas = new Float32Array(maxCount);
        const colorMix = new Float32Array(maxCount);
        const randomDir = new Float32Array(maxCount * 3);

        // Initialize with random starting protein
        const startProtein = proteins[currentProteinIndex];
        for (let i = 0; i < maxCount; i++) {
            if (i < startProtein.count) {
                positions[i * 3] = startProtein.positions[i * 3];
                positions[i * 3 + 1] = startProtein.positions[i * 3 + 1];
                positions[i * 3 + 2] = startProtein.positions[i * 3 + 2];
                alphas[i] = 1.0;
            } else {
                positions[i * 3] = 0; positions[i * 3 + 1] = 0; positions[i * 3 + 2] = 0;
                alphas[i] = 0.0;
            }
            // Target is same as current initially
            targetPositions[i * 3] = positions[i * 3];
            targetPositions[i * 3 + 1] = positions[i * 3 + 1];
            targetPositions[i * 3 + 2] = positions[i * 3 + 2];
            targetAlphas[i] = alphas[i];

            colorMix[i] = Math.random();

            // Random direction for explosion
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos((Math.random() * 2) - 1);
            randomDir[i * 3] = Math.sin(phi) * Math.cos(theta);
            randomDir[i * 3 + 1] = Math.sin(phi) * Math.sin(theta);
            randomDir[i * 3 + 2] = Math.cos(phi);
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('targetPosition', new THREE.BufferAttribute(targetPositions, 3));
        geometry.setAttribute('alpha', new THREE.BufferAttribute(alphas, 1));
        geometry.setAttribute('targetAlpha', new THREE.BufferAttribute(targetAlphas, 1));
        geometry.setAttribute('colorMix', new THREE.BufferAttribute(colorMix, 1));
        geometry.setAttribute('randomDir', new THREE.BufferAttribute(randomDir, 3));

        particles = new THREE.Points(geometry, particleMaterial);
        scene.add(particles);

        animate();
    }

    function prepareTransition() {
        const current = proteins[currentProteinIndex];
        const next = proteins[nextProteinIndex];

        const positions = geometry.attributes.position.array;
        const targetPositions = geometry.attributes.targetPosition.array;
        const alphas = geometry.attributes.alpha.array;
        const targetAlphas = geometry.attributes.targetAlpha.array;

        const maxCount = geometry.attributes.position.count;

        // 1. Update 'position' (Start State)
        positions.set(targetPositions);
        alphas.set(targetAlphas);

        // Spatial Sort Mapping

        // 1. Identify Active and Free particles
        // Since particles get scattered, we can't assume active ones are 0..current.count
        const activeIndices = [];
        const freeIndices = [];
        for (let i = 0; i < maxCount; i++) {
            if (alphas[i] > 0.5) {
                activeIndices.push(i);
            } else {
                freeIndices.push(i);
            }
        }

        // Sort active particles by current X position
        activeIndices.sort((a, b) => positions[a * 3] - positions[b * 3]);

        // 2. Get indices for target particles
        const nextIndices = new Int32Array(next.count);
        for (let i = 0; i < next.count; i++) nextIndices[i] = i;
        // Sort by target X position
        nextIndices.sort((a, b) => next.positions[a * 3] - next.positions[b * 3]);

        const activeCount = activeIndices.length;
        const targetCount = next.count;

        if (activeCount > targetCount) {
            // Shrinking: Select subset of active to map to all targets
            // We want to map 'targetCount' active particles to 'targetCount' target particles.
            // We should pick them evenly from the sorted active list.

            const step = activeCount / targetCount;
            const keptSet = new Set();

            for (let i = 0; i < targetCount; i++) {
                const activeSortedIdx = Math.floor(i * step);
                const currIdx = activeIndices[activeSortedIdx];
                const nextIdx = nextIndices[i];

                // Map
                targetPositions[currIdx * 3] = next.positions[nextIdx * 3];
                targetPositions[currIdx * 3 + 1] = next.positions[nextIdx * 3 + 1];
                targetPositions[currIdx * 3 + 2] = next.positions[nextIdx * 3 + 2];
                targetAlphas[currIdx] = 1.0;

                keptSet.add(currIdx);
            }

            // Fade out others
            for (let i = 0; i < activeCount; i++) {
                const currIdx = activeIndices[i];
                if (!keptSet.has(currIdx)) {
                    targetPositions[currIdx * 3] = positions[currIdx * 3]; // Stay put
                    targetPositions[currIdx * 3 + 1] = positions[currIdx * 3 + 1];
                    targetPositions[currIdx * 3 + 2] = positions[currIdx * 3 + 2];
                    targetAlphas[currIdx] = 0.0;
                }
            }

        } else {
            // Growing: Map all active to subset of targets
            // We want to map 'activeCount' active particles to 'activeCount' target particles.
            // We should pick the targets evenly.

            const step = targetCount / activeCount;
            const usedTargetSet = new Set();

            for (let i = 0; i < activeCount; i++) {
                const targetSortedIdx = Math.floor(i * step);
                const currIdx = activeIndices[i];
                const nextIdx = nextIndices[targetSortedIdx];

                // Map
                targetPositions[currIdx * 3] = next.positions[nextIdx * 3];
                targetPositions[currIdx * 3 + 1] = next.positions[nextIdx * 3 + 1];
                targetPositions[currIdx * 3 + 2] = next.positions[nextIdx * 3 + 2];
                targetAlphas[currIdx] = 1.0;

                usedTargetSet.add(nextIdx);
            }

            // Fill remaining targets with free particles
            for (let i = 0; i < targetCount; i++) {
                const nextIdx = nextIndices[i];
                if (!usedTargetSet.has(nextIdx)) {
                    if (freeIndices.length > 0) {
                        const freeIdx = freeIndices.pop();

                        // Start invisible at target
                        positions[freeIdx * 3] = next.positions[nextIdx * 3];
                        positions[freeIdx * 3 + 1] = next.positions[nextIdx * 3 + 1];
                        positions[freeIdx * 3 + 2] = next.positions[nextIdx * 3 + 2];
                        alphas[freeIdx] = 0.0;

                        // End visible at target
                        targetPositions[freeIdx * 3] = next.positions[nextIdx * 3];
                        targetPositions[freeIdx * 3 + 1] = next.positions[nextIdx * 3 + 1];
                        targetPositions[freeIdx * 3 + 2] = next.positions[nextIdx * 3 + 2];
                        targetAlphas[freeIdx] = 1.0;
                    } else {
                        console.warn("Not enough free particles");
                    }
                }
            }
        }

        // Ensure remaining free particles stay hidden
        for (const freeIdx of freeIndices) {
            targetAlphas[freeIdx] = 0.0;
            alphas[freeIdx] = 0.0;
        }

        geometry.attributes.position.needsUpdate = true;
        geometry.attributes.targetPosition.needsUpdate = true;
        geometry.attributes.alpha.needsUpdate = true;
        geometry.attributes.targetAlpha.needsUpdate = true;
    }

    function animate() {
        requestAnimationFrame(animate);

        const now = performance.now();

        // Update time uniform for shader
        particleMaterial.uniforms.time.value = now * 0.001;

        if (!isPaused) {
            const timeSinceChange = now - lastStateChangeTime;

            if (state === 'HOLD') {
                if (timeSinceChange > HOLD_DURATION) {
                    state = 'TRANSITION';
                    lastStateChangeTime = now;

                    nextProteinIndex = (currentProteinIndex + 1) % proteins.length;
                    // console.log(`Transitioning to ${proteins[nextProteinIndex].name}`);

                    prepareTransition();
                    particleMaterial.uniforms.transitionProgress.value = 0.0;
                }
            } else if (state === 'TRANSITION') {
                if (timeSinceChange > TRANSITION_DURATION) {
                    state = 'HOLD';
                    lastStateChangeTime = now;
                    currentProteinIndex = nextProteinIndex;
                    particleMaterial.uniforms.transitionProgress.value = 1.0;
                } else {
                    const progress = timeSinceChange / TRANSITION_DURATION;
                    const eased = progress < .5 ? 2 * progress * progress : -1 + (4 - 2 * progress) * progress;
                    particleMaterial.uniforms.transitionProgress.value = eased;
                }
            }
        } else {
            // If paused, just keep updating lastStateChangeTime so we don't jump when unpaused
            lastStateChangeTime = now - (state === 'TRANSITION' ? (particleMaterial.uniforms.transitionProgress.value * TRANSITION_DURATION) : 0);
        }

        // Rotation
        const time = now * 0.001;
        particles.rotation.y = (mouseX * 0.5);
        particles.rotation.x = (-mouseY * 0.5);

        renderer.render(scene, camera);
    }

    loadProteins();
});
