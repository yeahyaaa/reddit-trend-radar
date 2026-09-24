@echo off
setlocal enabledelayedexpansion
title Reddit Trend Radar

rem Asks for the two things that change between runs and leaves the rest alone.
rem Everything here is also available directly: python -m radar.cli --help

echo.
echo   Reddit Trend Radar
echo   ------------------
echo.
echo   Which communities? Names, r/ prefixes or pasted Reddit links,
echo   separated by spaces. Leave empty for the defaults.
echo.
echo     example:  news soccer technology
echo     example:  https://www.reddit.com/r/news/  r/soccer
echo.
set "SUBS="
set /p "SUBS=  Communities: "

echo.
echo   Over what period?
echo.
echo     1  today
echo     2  this week      (default)
echo     3  this month
echo     4  this year
echo.
set "CHOICE="
set /p "CHOICE=  Period [1-4]: "

if "%CHOICE%"=="1" set "PERIOD=day"
if "%CHOICE%"=="2" set "PERIOD=week"
if "%CHOICE%"=="3" set "PERIOD=month"
if "%CHOICE%"=="4" set "PERIOD=year"
if not defined PERIOD set "PERIOD=week"

echo.
echo   How many posts per community? Leave empty for 20.
set "TOP="
set /p "TOP=  Posts: "
if not defined TOP set "TOP=20"

rem The model step is only offered when a key is actually configured.
set "USEAI="
if defined ANTHROPIC_API_KEY set "USEAI=1"
if defined OPENAI_API_KEY set "USEAI=1"
if defined GEMINI_API_KEY set "USEAI=1"
if defined OPENROUTER_API_KEY set "USEAI=1"
if exist ".env" set "USEAI=1"

set "AIFLAG="
if defined USEAI (
  echo.
  echo   Group the posts into stories with a language model? This calls your
  echo   API provider and costs whatever they charge for one request.
  set "WANTAI="
  set /p "WANTAI=  Use the model? [y/N]: "
  if /i "!WANTAI!"=="y" set "AIFLAG=--ai"
)

rem One dated folder per run, so nothing overwrites last week's briefing.
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "TODAY=%%d"
set "OUT=reports\%TODAY%-%PERIOD%"
if not exist "%OUT%" mkdir "%OUT%"

set "ARGS=-p %PERIOD% -n %TOP% %AIFLAG%"
if defined SUBS set "ARGS=%ARGS% -s %SUBS%"

echo.
echo   Reading %PERIOD%, top %TOP% per community...
echo.

python -m radar.cli %ARGS% ^
  -o "%OUT%\report.md" ^
  --csv "%OUT%\report.csv" ^
  --xlsx "%OUT%\report.xlsx" ^
  --tex "%OUT%\report.tex"

if errorlevel 1 goto failed

rem Compile the PDF only if a LaTeX distribution is actually installed.
where pdflatex >nul 2>&1
if %errorlevel%==0 (
  echo.
  echo   Compiling the PDF...
  pushd "%OUT%"
  pdflatex -interaction=nonstopmode -halt-on-error report.tex >nul 2>&1
  del /q report.aux report.log report.out 2>nul
  popd
)

echo.
echo   Done. Files are in %OUT%
echo.
explorer "%OUT%"
goto end

:failed
echo.
echo   The run did not finish. Scroll up for the reason.
echo.

:end
pause
endlocal
