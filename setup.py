from setuptools import setup, find_packages

setup(name='gym',
      version='0.1',
      description='Gym Framework',
      author='Raphael Vicente Rosa',
      namespace_packages=["gym"],
      packages=find_packages(exclude=("tests",)),
      scripts=["gym/agent/gym-agent",
               "gym/monitor/gym-monitor",
               "gym/manager/gym-manager",
               "gym/player/gym-player"],
      install_requires = [
        'asyncio',
        'aiohttp',
        'psutil',
        'PyYAML',
        'pandas',
        'seaborn',
        'jinja2',
        'elasticsearch',
        'docker-py'
      ],
      include_package_data=True,
)
