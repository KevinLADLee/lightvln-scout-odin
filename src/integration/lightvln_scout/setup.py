from glob import glob

from setuptools import find_packages, setup

setup(
    name="lightvln_scout",
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/lightvln_scout"],
        ),
        ("share/lightvln_scout", ["package.xml"]),
        ("share/lightvln_scout/launch", glob("launch/*.launch.py")),
        ("share/lightvln_scout/config", glob("config/*.yaml")),
        ("share/lightvln_scout/web", glob("web/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=False,
    maintainer="LightVLN Scout maintainers",
    maintainer_email="maintainers@example.com",
    description="LightNav integration and safety adapter for Scout Mini with Odin1",
    license="GPL-3.0-or-later",
    entry_points={
        "console_scripts": [
            "scout_adapter = lightvln_scout.node:main",
            "scout_vln_client = lightvln_scout.vln_client_adapter:main",
            "scout_vln_web = lightvln_scout.vln_web_adapter:main",
        ]
    },
)
