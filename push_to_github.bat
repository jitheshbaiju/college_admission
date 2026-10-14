@echo off
set "PATH=%LOCALAPPDATA%\Programs\MinGit\cmd;%PATH%"
echo Pushing to GitHub (https://github.com/jitheshbaiju/college_admission.git)...
git push -u origin main
pause
