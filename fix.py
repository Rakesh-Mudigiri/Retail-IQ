import os, re

files = ['reports.html', 'products.html', 'prediction.html', 'customers.html', 'about.html']
dir_path = 'c:/Users/L/OneDrive/Desktop/ABCDE/templates/'

auth_block = re.compile(r'<script>\s*if\(localStorage\.getItem\(\'isLoggedIn\'\) !== \'true\'\)\s*\{\s*window\.location\.href = \'/login\';\s*\}\s*function logout\(\)\s*\{\s*localStorage\.removeItem\(\'isLoggedIn\'\);\s*window\.location\.href = \'/login\';\s*\}\s*</script>', re.DOTALL)

logout_icon = re.compile(r'<i class="bi bi-person-circle fs-4 text-primary" style="cursor: pointer;" onclick="logout\(\)" title="Logout"></i>')
new_logout = '<a href="/logout" title="Logout" class="text-primary"><i class="bi bi-box-arrow-right fs-4"></i></a>'

for f in files:
    p = os.path.join(dir_path, f)
    try:
        with open(p, 'r', encoding='utf-8') as file:
            c = file.read()
        
        c = auth_block.sub('', c)
        c = logout_icon.sub(new_logout, c)
        
        with open(p, 'w', encoding='utf-8') as file:
            file.write(c)
        print(f"Fixed {f}")
    except Exception as e:
        print(f"Skipping {f} - {e}")
