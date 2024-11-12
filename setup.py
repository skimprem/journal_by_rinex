from setuptools import setup, find_packages

setup(
    name="journal_by_rinex",
    version="1.0.0",
    description="GNSS Journal Creator",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Roman Sermiagin",
    author_email="roman.sermiagin@gmail.com",
    url="https://github.com/yourusername/my_package",  # Replace with your URL
    packages=find_packages(),
    package_data={
        'journal_by_rinex': ['images/*.png']  # Include all PNG images in the 'images' folder
    },
    include_package_data=True,
    install_requires=[
        "tk",             # Tkinter for GUI
        "georinex",       # For RINEX file processing
        "pyproj",         # For geodetic transformations
        "pylatex",        # For PDF generation
        "pypandoc"        # For DOCX generation
    ],
    entry_points={
        'console_scripts': [
            'journal_by_rinex=journal_by_rinex.main:run_app'  # Command to run the application
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
