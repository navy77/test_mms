@echo off
SETLOCAL EnableDelayedExpansion
title MMS System Installer (Windows Wizard)

cls
echo ===================================================
echo       MMS SYSTEM OFFLINE INSTALLATION WIZARD       
echo ===================================================
echo.
echo This wizard will guide you through the offline installation.
echo.
echo [Step 1 of 4] Checking Prerequisites
echo ---------------------------------------------------
docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Docker is not installed or not running.
    echo Please install Docker and start Docker Desktop, then try again.
    echo.
    pause
    exit /b 1
)
echo [OK] Docker is installed and running.
echo.
set /p "="<nul & echo Press [Enter] to go to the next step... & pause >nul

cls
echo ===================================================
echo [Step 2 of 4] Loading Docker Images (.tar)
echo ---------------------------------------------------
echo This step will load the packaged offline images.
echo It may take a few minutes depending on your disk speed.
echo.
set /p CONFIRM="Ready to load images? [Y/n]: "
if /I "!CONFIRM!"=="n" (
    echo [INFO] Skip loading images.
) else (
    if not exist "image" (
        echo [ERROR] 'image' folder not found.
        pause
        exit /b 1
    )
    for %%f in (image\*.tar) do (
        echo Loading: %%f...
        docker load -i "%%f"
    )
    echo.
    echo [OK] All images loaded successfully.
)
echo.
set /p "="<nul & echo Press [Enter] to go to the next step... & pause >nul

cls
echo ===================================================
echo [Step 3 of 4] Checking Network Configuration
echo ---------------------------------------------------
echo Checking if Docker network 'mms-network' exists...
docker network inspect mms-network >nul 2>&1
if !errorlevel! neq 0 (
    echo Network 'mms-network' not found. Creating it now...
    docker network create mms-network
    echo [OK] Created network 'mms-network'.
) else (
    echo [OK] Network 'mms-network' already exists.
)
echo.
set /p "="<nul & echo Press [Enter] to go to the next step... & pause >nul

cls
echo ===================================================
echo [Step 4 of 4] Deploying Applications
echo ---------------------------------------------------
echo Ready to launch MMS containers using docker-compose.
echo.
set /p DEPLOY_CONFIRM="Start deployment now? [Y/n]: "
if /I "!DEPLOY_CONFIRM!"=="n" (
    echo [INFO] Installation paused. You can start it later by running 'docker compose up -d'.
) else (
    if exist "docker-compose.yml" (
        echo Deploying containers in background...
        docker compose up -d
        echo.
        echo ===================================================
        echo     MMS Application Deployed Successfully.
        echo ===================================================
    ) else (
        echo [ERROR] docker-compose.yml not found.
        pause
        exit /b 1
    )
)
echo.
echo Press [Enter] to close this wizard.
pause >nul


