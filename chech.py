import os
import glob

def extract_code_files(project_directory='.'):
    """
    Extract all code files from project directory and combine into a single text output.
    Excludes database files, cache, and other non-code files.
    """
    
    # File extensions to include
    code_extensions = ['.py', '.js', '.html', '.css', '.txt', '.json', '.md', '.yml', '.yaml']
    
    # Files/directories to exclude
    exclude_patterns = [
        '*.db', '*.sqlite', '*.sqlite3',  # Database files
        '__pycache__', '*.pyc', '*.pyo',  # Python cache
        'node_modules', '.git', '.vscode', # Common directories
        '*.log', '*.tmp', 'temp*',        # Log and temp files
        'chech.py'                 # Exclude this script itself
    ]
    
    # Get all files in directory
    all_files = []
    for root, dirs, files in os.walk(project_directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not any(pattern.replace('*', '') in d for pattern in exclude_patterns if '*' in pattern)]
        dirs[:] = [d for d in dirs if d not in ['__pycache__', 'node_modules', '.git', '.vscode']]
        
        for file in files:
            file_path = os.path.join(root, file)
            # Check if file has allowed extension
            if any(file.endswith(ext) for ext in code_extensions):
                # Check if file matches exclude patterns
                if not any(
                    (pattern.startswith('*') and file.endswith(pattern[1:])) or 
                    (pattern.endswith('*') and file.startswith(pattern[:-1])) or
                    (pattern == file) or
                    (pattern in file_path)
                    for pattern in exclude_patterns
                ):
                    all_files.append(file_path)
    
    # Sort files for consistent output
    all_files.sort()
    
    # Extract content
    combined_content = []
    combined_content.append("=" * 80)
    combined_content.append("VIRTUAL FOOTBALL PREDICTION SYSTEM - CODE EXPORT")
    combined_content.append("=" * 80)
    combined_content.append(f"Extracted from: {os.path.abspath(project_directory)}")
    combined_content.append(f"Total files: {len(all_files)}")
    combined_content.append("=" * 80)
    combined_content.append("")
    
    for file_path in all_files:
        try:
            # Get relative path for cleaner display
            rel_path = os.path.relpath(file_path, project_directory)
            
            combined_content.append("-" * 60)
            combined_content.append(f"FILE: {rel_path}")
            combined_content.append("-" * 60)
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                combined_content.append(content)
            
            combined_content.append("")  # Empty line between files
            
        except Exception as e:
            combined_content.append(f"ERROR reading {rel_path}: {e}")
            combined_content.append("")
    
    return "\n".join(combined_content)

def save_extracted_code(output_file='project_code_export.txt', project_directory='.'):
    """Save extracted code to a file."""
    try:
        content = extract_code_files(project_directory)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Code extracted successfully!")
        print(f"Output file: {os.path.abspath(output_file)}")
        print(f"File size: {os.path.getsize(output_file):,} bytes")
        
        # Show file list for verification
        lines = content.split('\n')
        file_lines = [line for line in lines if line.startswith('FILE: ')]
        print(f"\nFiles included ({len(file_lines)}):")
        for line in file_lines[:10]:  # Show first 10
            print(f"  - {line.replace('FILE: ', '')}")
        if len(file_lines) > 10:
            print(f"  ... and {len(file_lines) - 10} more files")
            
    except Exception as e:
        print(f"Error: {e}")

def print_extracted_code(project_directory='.'):
    """Print extracted code to console (for copy-paste)."""
    try:
        content = extract_code_files(project_directory)
        print(content)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    
    # Get project directory from command line or use current directory
    project_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    
    print("Virtual Football Project Code Extractor")
    print("=" * 50)
    print("1. Save to file (recommended)")
    print("2. Print to console (for direct copy-paste)")
    print("3. Both")
    
    choice = input("\nChoose option (1-3): ").strip()
    
    if choice in ['1', '3']:
        output_filename = input("Output filename (default: project_code_export.txt): ").strip()
        if not output_filename:
            output_filename = 'project_code_export.txt'
        save_extracted_code(output_filename, project_dir)
    
    if choice in ['2', '3']:
        print("\n" + "="*80)
        print("CONSOLE OUTPUT (copy everything below this line):")
        print("="*80)
        print_extracted_code(project_dir)