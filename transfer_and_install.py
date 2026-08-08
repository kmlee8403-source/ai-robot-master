import sys
import os
import argparse
import subprocess
import paramiko

PI_HOST = "192.168.137.100"
PI_USER = "pi"
PI_PASS = "0000"
REMOTE_DIR = "/home/pi/transferred_packages"

def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)
    return client

def run_remote_cmd(client, cmd):
    print(f"[Pi] Executing: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out:
        print(out)
    if err:
        print(f"Stderr: {err}")
    return out, err

def transfer_files(client, local_files):
    sftp = client.open_sftp()
    run_remote_cmd(client, f"mkdir -p {REMOTE_DIR}")
    remote_paths = []
    for lf in local_files:
        filename = os.path.basename(lf)
        rf = f"{REMOTE_DIR}/{filename}"
        print(f"[SFTP] Transferring {lf} -> {rf}")
        sftp.put(lf, rf)
        remote_paths.append(rf)
    sftp.close()
    return remote_paths

def install_pip(pkg_name):
    print(f"=== Downloading PyPI package: {pkg_name} ===")
    download_dir = os.path.abspath("downloaded_pkg")
    os.makedirs(download_dir, exist_ok=True)
    
    # Clean previous downloads
    for f in os.listdir(download_dir):
        os.remove(os.path.join(download_dir, f))

    # Download dependencies
    cmd = [
        sys.executable, "-m", "pip", "download",
        "--dest", download_dir,
        pkg_name
    ]
    print("Running:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Download warning/error:", res.stderr)
    
    files = [os.path.join(download_dir, f) for f in os.listdir(download_dir)]
    if not files:
        print("No files downloaded.")
        return

    client = get_ssh_client()
    try:
        transfer_files(client, files)
        print(f"=== Installing {pkg_name} on Raspberry Pi ===")
        run_remote_cmd(client, f"pip install --no-index --find-links={REMOTE_DIR} {pkg_name}")
    finally:
        client.close()

def install_deb(deb_path_or_url):
    client = get_ssh_client()
    try:
        if deb_path_or_url.startswith("http://") or deb_path_or_url.startswith("https://"):
            import urllib.request
            filename = os.path.basename(deb_path_or_url)
            local_file = os.path.abspath(filename)
            print(f"Downloading {deb_path_or_url} -> {local_file}")
            urllib.request.urlretrieve(deb_path_or_url, local_file)
        else:
            local_file = os.path.abspath(deb_path_or_url)

        if not os.path.exists(local_file):
            print(f"Error: {local_file} does not exist.")
            return

        transfer_files(client, [local_file])
        filename = os.path.basename(local_file)
        print(f"=== Installing {filename} on Raspberry Pi ===")
        run_remote_cmd(client, f"echo {PI_PASS} | sudo -S dpkg -i {REMOTE_DIR}/{filename}")
    finally:
        client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transfer and install packages to Raspberry Pi")
    parser.add_argument("--pip", help="PyPI package name to download and install on Pi")
    parser.add_argument("--deb", help="Local .deb file or URL to transfer and install on Pi")
    args = parser.parse_args()

    if args.pip:
        install_pip(args.pip)
    elif args.deb:
        install_deb(args.deb)
    else:
        print("Usage: python transfer_and_install.py --pip <package_name>  OR  --deb <deb_file_or_url>")
