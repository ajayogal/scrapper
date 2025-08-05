cd ./
source venv/bin/activate

# runs in port 5173
cd grocery-frontend 
npm run dev



# runs in port 5002
cd grocery-api 
pip install -r requirements.txt
python src/main.py

=====================================

**macOS:**
```bash
# Using Homebrew
brew install --cask google-chrome
# or
brew install --cask chromium
```

**Ubuntu/Debian:**
```bash
# Install Chromium
sudo apt update
sudo apt install chromium-browser


# IGA
cd iga/
pip install -r requirements.txt
python iga_scraper.py bread --sort price --page 2
