# AISE 2024 - Final Project: Neural Operators for PDEs

**Author:** Oliver Nagl (22-920-151)  
**Course:** Artificial Intelligence for Science and Engineering (AISE)  
**Institution:** ETH Zurich  
**Date:** 2025

## Overview

This repository contains the implementation of three neural network approaches for solving/finding partial differential equations (PDEs) using modern deep learning techniques. The project explores Fourier Neural Operators (FNOs), PDE discovery methods, and phase field dynamics modeling.

## Project Structure

```
├── Part1/                          # Fourier Neural Operators for Wave Equation
├── Part2/                          # PDE Discovery and System Identification
├── Part3/                          # Phase Field Dynamics (Allen-Cahn Equation)
├── Plots/                          # Generated visualizations and results
├── requirements.txt                # Python dependencies
├── *.pdf                          # Project reports and documentation
└── README.md                      # This file
```

## Part 1: Fourier Neural Operators for 1D Wave Equation

### Description
Implementation of Fourier Neural Operators (FNOs) for solving the 1D wave equation. FNOs leverage the spectral properties of PDEs by performing convolutions in Fourier space, making them highly effective for periodic and quasi-periodic problems.

### Key Features
- **Spectral Convolution Layer**: Custom implementation of Fourier-domain convolutions
- **Time-dependent and Time-independent Models**: Support for both static and temporal predictions
- **Multi-resolution Training**: Training on different spatial resolutions (32, 64, 96, 128 grid points)
- **Out-of-distribution Testing**: Evaluation on unseen resolutions and time horizons

### Files
- `FNO_model.py` - Core FNO architecture implementation
- `FNO_model_time_dependent.py` - Time-continuous FNO variant
- `FNO_train_t0_t1.py` - Training script for t₀→t₁ prediction
- `FNO_train_all2all.py` - Training script for all-to-all time prediction
- `FNO_test_t0_t1.py` - Testing script for single time step prediction
- `FNO_test_all2all.py` - Testing script for multi-time prediction
- `FNO_visualisation.py` - Visualization utilities

### Usage
```bash
# Train FNO for t0 to t1 prediction
python Part1/FNO_train_t0_t1.py

# Train FNO for all-to-all prediction
python Part1/FNO_train_all2all.py

# Test trained models
python Part1/FNO_test_t0_t1.py
python Part1/FNO_test_all2all.py
```

## Part 2: PDE Discovery and System Identification

### Description
Implementation of neural network-based PDE discovery methods that can identify unknown governing equations from observational data. The approach combines function approximation with symbolic regression to discover interpretable PDE terms.

### Key Features
- **Gradient-based Discovery**: Automatic computation of spatial and temporal derivatives
- **Sparse Regression**: Ridge regression for term selection and coefficient estimation
- **Multi-variable Systems**: Support for coupled PDE systems (u, v variables)
- **Generalization Analysis**: Cross-validation on different PDE families

### Files
- `PDE_Find_main.py` - Main training and discovery pipeline
- `PDE_Find_models.py` - Neural network architectures for PDE discovery
- `PDE_Find_utility.py` - Utility functions for data processing and visualization
- `PDE_Find_generalisation_main.py` - Generalization testing framework
- `PDE_Find_generalisation_utility.py` - Utilities for generalization analysis

### Usage
```bash
# Run PDE discovery on dataset
python Part2/PDE_Find_main.py

# Test generalization capabilities
python Part2/PDE_Find_generalisation_main.py
```

### Discovered PDE Terms
The system can identify terms such as:
- Linear terms: `u`, `v`
- Diffusion terms: `∂²u/∂x²`, `∂²v/∂y²`
- Advection terms: `∂u/∂x`, `∂v/∂y`
- Nonlinear terms: `u²`, `v²`, `u·∂u/∂x`
- Coupled terms: `A²u`, `A²v` where `A² = u² + v²`

## Part 3: Phase Field Dynamics (Allen-Cahn Equation)

### Description
Neural network solution for the Allen-Cahn equation, a fundamental model in phase field theory used to describe phase transitions and interface dynamics. The implementation includes curriculum learning and handles multiple scales through the epsilon parameter.

### Key Features
- **Curriculum Learning**: Progressive training strategy across different epsilon values
- **Multi-scale Modeling**: Handles sharp and diffuse interfaces (ε ∈ [0.003125, 1])
- **Diverse Initial Conditions**: Fourier, GMM, and piecewise linear initial conditions
- **Temporal Extrapolation**: Prediction beyond training time horizons
- **Out-of-distribution Testing**: Evaluation on unseen epsilon values and time scales

### Files
- `PhaseFieldDynamics_main.py` - Main training and testing pipeline
- `PhaseFieldDynamics_model.py` - Neural network architecture
- `PhaseFieldDynamics_utility.py` - Utility functions and data processing
- `PhaseFieldDynamics_data_generation.py` - Allen-Cahn data generation

### Usage
```bash
# Generate Allen-Cahn dataset
python Part3/PhaseFieldDynamics_data_generation.py

# Train phase field model
python Part3/PhaseFieldDynamics_main.py
```

### Allen-Cahn Equation
The implemented model solves:
```
∂u/∂t = ε²∇²u + u - u³
```
where ε controls the interface width and u represents the phase field variable.

## Installation and Setup

### Requirements
- Python 3.8+
- PyTorch 2.5.0
- NumPy 1.26.4
- Matplotlib 3.9.2
- scikit-learn 1.5.2
- SciPy 1.14.1

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Hardware Requirements
- GPU recommended for training (CUDA support)
- Minimum 8GB RAM
- 10GB+ storage for datasets and models

## Data

**Note**: Due to GitHub's file size limitations, large data files, trained models, and generated visualizations are not included in this repository. The data can be regenerated using the provided scripts.

### Part 1: Wave Equation Data
- Training data: 1D wave solutions at multiple resolutions
- Test data: Out-of-distribution resolutions and time horizons
- Format: NumPy arrays (.npy files)
- **Status**: Not hosted (can be generated locally)

### Part 2: PDE Discovery Data
- Synthetic PDE solutions with known governing equations
- Multiple variable systems (u, v) with coupled dynamics
- Format: Compressed NumPy (.npz files)
- **Status**: Not hosted (can be generated locally)

### Part 3: Allen-Cahn Data
- Generated using finite difference schemes
- Multiple epsilon values and initial condition types
- Format: NumPy arrays with metadata
- **Status**: Not hosted (use `PhaseFieldDynamics_data_generation.py` to generate)

## Results and Visualizations

**Note**: Generated plots, model files, and prediction results are not included in the repository due to size constraints. Run the training and testing scripts to reproduce these outputs locally.

The `Plots/` directory (when generated) contains:
- Wave equation predictions and error analysis
- PDE discovery results with identified terms
- Allen-Cahn phase evolution visualizations
- Performance comparisons across different scales

## Key Contributions

1. **Efficient FNO Implementation**: Optimized Fourier Neural Operator with spectral convolutions
2. **Robust PDE Discovery**: Gradient-based approach for identifying unknown governing equations
3. **Multi-scale Phase Field Modeling**: Curriculum learning strategy for handling multiple spatial scales
4. **Comprehensive Evaluation**: Extensive testing on out-of-distribution scenarios

## Performance Metrics

- **Relative L2 Error**: Primary metric for solution accuracy
- **Generalization Error**: Performance on unseen parameters/conditions
- **Computational Efficiency**: Training time and inference speed
- **Stability Analysis**: Long-term prediction accuracy

## Future Extensions

- Extension to 2D/3D problems
- Integration with physics-informed neural networks (PINNs)
- Real-time inference optimization
- Uncertainty quantification

## References

- Li, Z., et al. "Fourier Neural Operator for Parametric Partial Differential Equations." ICLR 2021.
- Raissi, M., et al. "Physics-informed neural networks: A deep learning framework for solving forward and inverse problems involving nonlinear partial differential equations." Journal of Computational Physics, 2019.
- Allen, S. M., & Cahn, J. W. "A microscopic theory for antiphase boundary motion and its application to antiphase domain coarsening." Acta Metallurgica, 1979.

## License

This project is part of academic coursework at ETH Zurich. Please contact the author for usage permissions.

## Contact

**Oliver Nagl**  
ETH Zurich  
LinkedIn: [https://www.linkedin.com/in/oliver-nagl-41a40a1b0/](https://www.linkedin.com/in/oliver-nagl-41a40a1b0/)

---

*This repository represents the final project submission for AISE 2024 at ETH Zurich.*
