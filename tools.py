"""
工具定义

定义 Agent 可用的所有工具
"""
from langchain_core.tools import tool
from datetime import datetime
from skill_manager import skill_manager
import subprocess
import os
import dotenv

dotenv.load_dotenv('../../../.env')


@tool
def add_number(a: int, b: int) -> int:
    """add two numbers."""
    return a + b

@tool
def bash(command: str) -> str:
    """执行 bash 命令并返回结果
    
    Args:
        command: 要执行的 bash 命令
        
    Returns:
        命令执行结果（标准输出或错误信息）
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            return f"错误 (exit code {result.returncode}):\n{result.stderr}"
        
        return result.stdout.strip() or "命令执行成功（无输出）"
        
    except subprocess.TimeoutExpired:
        return "错误: 命令执行超时（60秒）"
    except Exception as e:
        return f"错误: {str(e)}"


@tool
def load_skill(skill_name: str) -> str:
    """加载指定技能的详细指令
    
    Args:
        skill_name: 技能名称，如 'github', 'weather' 等
    
    Returns:
        技能的详细指令内容
    """
    return skill_manager.load_skill(skill_name)


def get_all_tools():
    """获取所有工具列表"""
    return [bash, load_skill,add_number]


if __name__ == '__main__':
    print(bash.invoke('ls -la'))
