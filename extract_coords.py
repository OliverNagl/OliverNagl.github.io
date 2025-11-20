import struct

def extract_coords(pdb_file, output_file):
    coords = []
    count = 0
    
    print(f"Reading {pdb_file}...")
    with open(pdb_file, 'r') as f:
        for line in f:
            if line.startswith("ATOM"):
                try:
                    # PDB format:
                    # x: 30-38
                    # y: 38-46
                    # z: 46-54
                    x = float(line[30:38].strip())
                    y = float(line[38:46].strip())
                    z = float(line[46:54].strip())
                    coords.extend([x, y, z])
                    count += 1
                except ValueError:
                    continue
    
    print(f"Extracted {count} atoms.")
    
    print(f"Writing to {output_file}...")
    with open(output_file, 'wb') as f:
        # Pack as little-endian floats
        f.write(struct.pack(f'<{len(coords)}f', *coords))
        
    print("Done.")

if __name__ == "__main__":
    extract_coords("AaLS_centered.pdb", "protein_coords.bin")
