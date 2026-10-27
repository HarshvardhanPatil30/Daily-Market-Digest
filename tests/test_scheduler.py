import pytest
from services.scheduler import setup_task,windows_task_command
def test_scheduler_is_safe():
    assert 'schtasks' in windows_task_command('/tmp/project')
    with pytest.raises(PermissionError): setup_task('/tmp/project',False)
