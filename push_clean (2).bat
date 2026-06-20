@echo off
cd /d "D:\MULTIMI_VAGI1\Test11\Test11_Final_OK"

(
echo === Sterg istoricul Git vechi ===
rmdir /s /q .git

echo === Reinitializare repo ===
git init
git remote add origin https://github.com/DoruPospai/titus-clinical-app.git

echo === Adaugare fisiere ===
git add -A

echo === Commit ===
git commit -m "TITUS clinical platform"

echo === Branch main ===
git branch -M main

echo === Push (force) ===
git push -u origin main --force

echo.
echo ===================================
echo TERMINAT.
echo ===================================
) > push_log.txt 2>&1

echo Rezultatul a fost salvat in push_log.txt
echo Deschid fisierul...
notepad push_log.txt
