from distutils.core import setup

setup(
    name="WikEdDiff",
    version="1.2.4",
    description="Visual inline-style difference engine with block move support.",
    author="Jakub Klinkovský",
    author_email="j.l.k@gmx.com",
    url="https://github.com/lahwaacz/python-wikeddiff",
    license="GPLv3",
    packages=["WikEdDiff"],
    scripts=["diff.py"],
    install_requires=["namedlist"]
)
