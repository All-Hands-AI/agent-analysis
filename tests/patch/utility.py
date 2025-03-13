import tempfile
import subprocess
from pathlib import Path

def git_diff(before: str, after: str, filename: str) -> str:
    """
    Generate an actual git diff between two strings by utilizing git command line tool.
        
    Raises:
        RuntimeError: If git is not installed or if there's an error running git commands
    """
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Check if git is installed
        try:
            subprocess.run(["git", "--version"], check=True, 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            raise RuntimeError("Git is not installed or not in the system PATH. Please install git to use this function.")
        except subprocess.SubprocessError as e:
            raise RuntimeError(f"Error verifying git installation: {str(e)}")
            
        # Initialize git repository
        try:
            subprocess.run(["git", "init"], cwd=temp_dir, check=True, 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.SubprocessError as e:
            raise RuntimeError(f"Failed to initialize git repository: {str(e)}")
        
        # Create file with old content
        file_path = temp_path / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(before)
        
        # Add and commit the file
        try:
            subprocess.run(["git", "add", filename], cwd=temp_dir, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "example@example.com"], cwd=temp_dir, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.name", "Example User"], cwd=temp_dir, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.SubprocessError as e:
            raise RuntimeError(f"Failed to commit initial file: {str(e)}")
        
        # Update file with new content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(after)
        
        # Run git diff and capture output
        try:
            result = subprocess.run(["git", "diff", filename], cwd=temp_dir, check=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout
        except subprocess.SubprocessError as e:
            raise RuntimeError(f"Failed to generate diff: {str(e)}")
