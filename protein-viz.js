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
    camera.position.z = 600;

    // Renderer Setup
    const renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        alpha: true,
        antialias: true
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Shader Material for per-particle opacity and morphing
    const particleMaterial = new THREE.ShaderMaterial({
        uniforms: {
            pixelRatio: { value: renderer.getPixelRatio() },
            color1: { value: new THREE.Color('#4ECDC4') },
            color2: { value: new THREE.Color('#26A69A') },
            transitionProgress: { value: 0.0 }
        },
        vertexShader: `
            attribute float alpha;
            attribute float colorMix;
            attribute vec3 targetPosition;
            attribute float targetAlpha;
            
            varying float vAlpha;
            varying float vColorMix;
            
            uniform float transitionProgress;

            void main() {
                // Interpolate position and alpha
                vec3 currentPos = mix(position, targetPosition, transitionProgress);
                vAlpha = mix(alpha, targetAlpha, transitionProgress);
                
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
    let nextProteinIndex = 1;
    let particles;
    let geometry;

    // Animation State
    const HOLD_DURATION = 10000; // 10 seconds
    const TRANSITION_DURATION = 5000; // 5 seconds
    let lastStateChangeTime = Date.now();
    let state = 'HOLD'; // 'HOLD' or 'TRANSITION'

    // Mouse Interaction
    let mouseX = 0;
    let mouseY = 0;
    document.addEventListener('mousemove', (event) => {
        mouseX = (event.clientX / window.innerWidth) * 2 - 1;
        mouseY = -(event.clientY / window.innerHeight) * 2 + 1;
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

                // Subsample if needed
                const step = 3;
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

        // Initialize with first protein
        const firstProtein = proteins[0];
        for (let i = 0; i < maxCount; i++) {
            if (i < firstProtein.count) {
                positions[i * 3] = firstProtein.positions[i * 3];
                positions[i * 3 + 1] = firstProtein.positions[i * 3 + 1];
                positions[i * 3 + 2] = firstProtein.positions[i * 3 + 2];
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
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('targetPosition', new THREE.BufferAttribute(targetPositions, 3));
        geometry.setAttribute('alpha', new THREE.BufferAttribute(alphas, 1));
        geometry.setAttribute('targetAlpha', new THREE.BufferAttribute(targetAlphas, 1));
        geometry.setAttribute('colorMix', new THREE.BufferAttribute(colorMix, 1));

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
        // Use .set() for fast copy
        positions.set(targetPositions);
        alphas.set(targetAlphas);

        // 2. Update 'targetPosition' (End State)
        for (let i = 0; i < maxCount; i++) {
            if (i < next.count) {
                targetPositions[i * 3] = next.positions[i * 3];
                targetPositions[i * 3 + 1] = next.positions[i * 3 + 1];
                targetPositions[i * 3 + 2] = next.positions[i * 3 + 2];
                targetAlphas[i] = 1.0;
            } else {
                // If not in next, it should fade out.
                // Stay at current position (which is now in 'positions').
                // So targetPosition should equal position (start state).
                targetPositions[i * 3] = positions[i * 3];
                targetPositions[i * 3 + 1] = positions[i * 3 + 1];
                targetPositions[i * 3 + 2] = positions[i * 3 + 2];
                targetAlphas[i] = 0.0;
            }

            // Handle "appear gradually" for new points
            // If it was hidden in the start state, we want it to appear at 'targetPositions'.
            // To prevent flying from 0,0,0, we set start 'positions' to 'targetPositions'.
            if (alphas[i] < 0.01) {
                positions[i * 3] = targetPositions[i * 3];
                positions[i * 3 + 1] = targetPositions[i * 3 + 1];
                positions[i * 3 + 2] = targetPositions[i * 3 + 2];
            }
        }

        geometry.attributes.position.needsUpdate = true;
        geometry.attributes.targetPosition.needsUpdate = true;
        geometry.attributes.alpha.needsUpdate = true;
        geometry.attributes.targetAlpha.needsUpdate = true;
    }

    function animate() {
        requestAnimationFrame(animate);

        const now = Date.now();
        const timeSinceChange = now - lastStateChangeTime;

        // Update Logic
        if (state === 'HOLD') {
            if (timeSinceChange > HOLD_DURATION) {
                state = 'TRANSITION';
                lastStateChangeTime = now;

                // Prepare next indices
                nextProteinIndex = (currentProteinIndex + 1) % proteins.length;
                console.log(`Transitioning from ${proteins[currentProteinIndex].name} to ${proteins[nextProteinIndex].name}`);

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
                // Ease in-out
                const eased = progress < .5 ? 2 * progress * progress : -1 + (4 - 2 * progress) * progress;
                particleMaterial.uniforms.transitionProgress.value = eased;
            }
        }

        // Rotation (Vibing + Mouse)
        const time = now * 0.001;
        particles.rotation.y = (mouseX * 0.5) + (time * 0.05);
        particles.rotation.x = (-mouseY * 0.5);

        renderer.render(scene, camera);
    }

    loadProteins();
});
