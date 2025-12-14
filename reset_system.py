
import shutil
import os

def reset_system():
    paths_to_clear = [
        "./chroma_db",
        "./architectures",
        "./maps",
        "./graphs",
        "./db"
    ]
    
    print("🧹 Cleaning up system data...")
    
    for path in paths_to_clear:
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                print(f"✅ Deleted: {path}")
            except Exception as e:
                print(f"❌ Failed to delete {path}: {e}")
        else:
            print(f"ℹ️  Path not found (already clean): {path}")

    print("✨ System reset complete. You can now restart the server.")

if __name__ == "__main__":
    reset_system()
