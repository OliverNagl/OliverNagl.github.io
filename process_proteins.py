import os
import struct
import json
import math

PROTEINS_DIR = 'Proteins'
OUTPUT_DIR = 'Protein_coords'

def parse_pdb(filepath):
    coords = []
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('ATOM') or line.startswith('HETATM'):
                try:
                    # PDB fixed width format
                    # x: 30-38, y: 38-46, z: 46-54
                    x = float(line[30:38].strip())
                    y = float(line[38:46].strip())
                    z = float(line[46:54].strip())
                    coords.extend([x, y, z])
                except ValueError:
                    continue
    return coords

def parse_cif(filepath):
    coords = []
    # Very basic CIF parser for coordinates
    # Assumes _atom_site.Cartn_x, _atom_site.Cartn_y, _atom_site.Cartn_z are present in the loop
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    in_atom_site_loop = False
    headers = []
    
    # Find the atom_site loop and headers
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('loop_'):
            # Check if this loop contains atom_site
            temp_headers = []
            j = i + 1
            is_atom_site = False
            while j < len(lines) and lines[j].strip().startswith('_'):
                header = lines[j].strip()
                temp_headers.append(header)
                if header.startswith('_atom_site.'):
                    is_atom_site = True
                j += 1
            
            if is_atom_site:
                headers = temp_headers
                in_atom_site_loop = True
                i = j 
                break
            else:
                i = j
        else:
            i += 1

    if not in_atom_site_loop:
        print(f"Warning: No atom_site loop found in {filepath}")
        return []

    # Map indices
    try:
        idx_x = headers.index('_atom_site.Cartn_x')
        idx_y = headers.index('_atom_site.Cartn_y')
        idx_z = headers.index('_atom_site.Cartn_z')
    except ValueError:
        print(f"Warning: Missing coordinate headers in {filepath}")
        return []

    # Parse data lines
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith('#') or line.startswith('loop_'):
            break # End of loop or file
        
        parts = line.split()
        # Handle potential quoting issues? For now assume simple space separation works for coords
        # CIF can be complex with quoted strings, but coords are usually simple numbers.
        
        if len(parts) > max(idx_x, idx_y, idx_z):
            try:
                x = float(parts[idx_x])
                y = float(parts[idx_y])
                z = float(parts[idx_z])
                coords.extend([x, y, z])
            except ValueError:
                pass
        i += 1
        
    return coords

def process_proteins():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    manifest = []
    
    # Get all files
    files = [f for f in os.listdir(PROTEINS_DIR) if f.endswith('.pdb') or f.endswith('.cif')]
    files.sort() # Ensure consistent order
    
    print(f"Found {len(files)} protein files.")

    for filename in files:
        filepath = os.path.join(PROTEINS_DIR, filename)
        print(f"Processing {filename}...")
        
        if filename.endswith('.pdb'):
            coords = parse_pdb(filepath)
        elif filename.endswith('.cif'):
            coords = parse_cif(filepath)
        else:
            continue
            
        if not coords:
            print(f"Warning: No coordinates found for {filename}")
            continue

        # Center the protein
        num_atoms = len(coords) // 3
        avg_x = sum(coords[0::3]) / num_atoms
        avg_y = sum(coords[1::3]) / num_atoms
        avg_z = sum(coords[2::3]) / num_atoms
        
        centered_coords = []
        for k in range(num_atoms):
            centered_coords.append(coords[k*3] - avg_x)
            centered_coords.append(coords[k*3+1] - avg_y)
            centered_coords.append(coords[k*3+2] - avg_z)

        # Save to binary
        output_filename = f"{os.path.splitext(filename)[0]}.bin"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        with open(output_path, 'wb') as f:
            f.write(struct.pack(f'{len(centered_coords)}f', *centered_coords))
            
        manifest.append({
            'name': filename,
            'file': output_filename,
            'count': num_atoms
        })
        print(f"Saved {output_filename} ({num_atoms} atoms)")

    # Save manifest
    with open(os.path.join(OUTPUT_DIR, 'protein_manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print("Done!")

if __name__ == "__main__":
    process_proteins()
