from pathlib import Path
def windows_task_command(project_dir):
    project=Path(project_dir).resolve(); python=project / ".venv" / "Scripts" / "python.exe"
    return f'schtasks /Create /TN "Daily Market Digest" /TR "\\\"{python}\\\" \\\"{project / "main.py"}\\\" run" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 16:15 /F'
def setup_task(project_dir, confirmed=False):
    if not confirmed: raise PermissionError("Scheduler changes require explicit --confirm. No task was created.")
    if __import__('platform').system() != 'Windows': raise RuntimeError("Windows Task Scheduler is only available on Windows.")
    import subprocess; return subprocess.run(windows_task_command(project_dir),shell=True,check=True,text=True,capture_output=True).stdout
