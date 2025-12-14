
import os

def generate_report(source_dir, output_file):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write("# Backend Codebase Dump\n\n")
        
        for root, dirs, files in os.walk(source_dir):
            # Skip common junk directories
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
            if '.git' in dirs:
                dirs.remove('.git')
            if '.pytest_cache' in dirs:
                dirs.remove('.pytest_cache')
            if 'venv' in dirs:
                dirs.remove('venv')
            
            for file in files:
                if file.endswith('.pyc'):
                    continue
                if file == os.path.basename(output_file):
                    continue
                if file == os.path.basename(__file__):
                    continue
                if file.endswith('.md') and 'walkthrough' in file: # skip huge logs if any
                     continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, start=os.path.dirname(source_dir)) # relative to project root usually, or just backend
                
                # Make path relative to backend parent folder for clarity e.g. "backend/app/main.py"
                # source_dir is ".../backend", so relpath from source_dir gives "app/main.py". 
                # Let's verify what user wants. "file adress". 
                # Let's use the full relative path from the script execution location or the 'backend' folder explicitly.
                
                display_path = os.path.relpath(file_path, start=os.path.dirname(source_dir))
                
                outfile.write(f"## File: `{display_path.replace(os.sep, '/')}`\n")
                outfile.write("```\n")
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"Error reading file: {e}")
                
                outfile.write("\n```\n\n")
    
    print(f"✅ Generated report at {output_file}")

if __name__ == "__main__":
    # Assumes script is in root or we specify paths
    # User path: c:/Users/User/Workspace/gdg/kiwi/backend
    # Let's target the backend folder specifically
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
    OUTPUT_FILE = os.path.join(BASE_DIR, 'backend_codebase.md')
    
    if os.path.exists(BACKEND_DIR):
        generate_report(BACKEND_DIR, OUTPUT_FILE)
    else:
        print(f"❌ Could not find backend directory at {BACKEND_DIR}")
