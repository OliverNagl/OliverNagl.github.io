document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('protein-container');
    const canvas = document.getElementById('proteinCanvas');

    if (!container || !canvas) {
        return;
    }

    if (container.clientWidth === 0 || container.clientHeight === 0) {
        // Simple retry mechanism could go here, but let's just log for now
    }

    // Scene Setup
    const scene = new THREE.Scene();

    // Camera Setup
    const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.z = 30;

    // Renderer Setup
    const renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        alpha: true,
        antialias: true
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Particle System
    const particleCount = 3000;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const originalPositions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    // Generate a random protein-like structure using a curve
    const points = [];
    const segmentCount = 20;
    for (let i = 0; i < segmentCount; i++) {
        points.push(new THREE.Vector3(
            (Math.random() - 0.5) * 20,
            (Math.random() - 0.5) * 20,
            (Math.random() - 0.5) * 20
        ));
    }
    const curve = new THREE.CatmullRomCurve3(points);
    curve.closed = false;

    const color1 = new THREE.Color('#4ECDC4');
    const color2 = new THREE.Color('#26A69A');

    for (let i = 0; i < particleCount; i++) {
        const t = i / particleCount;
        const point = curve.getPoint(t);

        // Add some randomness/volume around the curve
        const spread = 2.5;
        const x = point.x + (Math.random() - 0.5) * spread;
        const y = point.y + (Math.random() - 0.5) * spread;
        const z = point.z + (Math.random() - 0.5) * spread;

        positions[i * 3] = x;
        positions[i * 3 + 1] = y;
        positions[i * 3 + 2] = z;

        originalPositions[i * 3] = x;
        originalPositions[i * 3 + 1] = y;
        originalPositions[i * 3 + 2] = z;

        // Color gradient
        const mixedColor = color1.clone().lerp(color2, Math.random());
        colors[i * 3] = mixedColor.r;
        colors[i * 3 + 1] = mixedColor.g;
        colors[i * 3 + 2] = mixedColor.b;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
        size: 0.15,
        vertexColors: true,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending
    });

    const particles = new THREE.Points(geometry, material);
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
        particles.rotation.y = time * 0.1;
        particles.rotation.z = time * 0.05;

        const positions = particles.geometry.attributes.position.array;

        // Unraveling factor based on scroll
        // Normalize scroll based on viewport height (start unraveling immediately, max out at 100vh)
        const unravelFactor = Math.min(Math.max(scrollY / window.innerHeight, 0), 2.0);

        for (let i = 0; i < particleCount; i++) {
            const ix = i * 3;
            const iy = i * 3 + 1;
            const iz = i * 3 + 2;

            // Original position
            const ox = originalPositions[ix];
            const oy = originalPositions[iy];
            const oz = originalPositions[iz];

            // Vibing noise
            const vibeX = Math.sin(time + ox) * 0.2;
            const vibeY = Math.cos(time + oy) * 0.2;
            const vibeZ = Math.sin(time + oz) * 0.2;

            // Unraveling direction (explode outwards from center)
            // We can use the original position as a direction vector
            const dist = Math.sqrt(ox * ox + oy * oy + oz * oz);
            const dirX = ox / (dist || 1);
            const dirY = oy / (dist || 1);
            const dirZ = oz / (dist || 1);

            // Apply forces
            // 1. Vibe: always present
            // 2. Unravel: increases with scroll.
            //    We want it to explode significantly.

            const explosionStrength = unravelFactor * 30; // Multiplier for distance
            const noiseStrength = unravelFactor * 5; // Add chaos as it expands

            positions[ix] = ox + vibeX + (dirX * explosionStrength) + (Math.random() - 0.5) * noiseStrength;
            positions[iy] = oy + vibeY + (dirY * explosionStrength) + (Math.random() - 0.5) * noiseStrength;
            positions[iz] = oz + vibeZ + (dirZ * explosionStrength) + (Math.random() - 0.5) * noiseStrength;
        }

        particles.geometry.attributes.position.needsUpdate = true;

        renderer.render(scene, camera);
    }

    animate();
});
