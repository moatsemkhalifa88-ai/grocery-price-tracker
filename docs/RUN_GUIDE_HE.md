# מדריך הפעלה — שלב אחרי שלב (Windows + VS Code)

> זמן משוער להפעלה ראשונה: 30–45 דקות. אם משהו נכשל, שלח לי את הקובץ `logs\pricetracker.log` ואת הודעת השגיאה.

## 0. מה צריך להתקין (פעם אחת)

| כלי | למה | איפה |
|---|---|---|
| **Python 3.12** | הפייפליין | python.org → Downloads → Windows. בהתקנה לסמן **Add python.exe to PATH** |
| **Node.js 22 LTS** | האתר | nodejs.org |
| **Git** | העלאה ל-GitHub | git-scm.com |
| **Power BI Desktop** | הדוח | Microsoft Store |

> למה 3.12 ולא הגרסה הכי חדשה? dbt עדיין לא תומך תמיד בגרסה האחרונה של Python. ה-Anaconda שלך לא מפריע — אנחנו עובדים בסביבה וירטואלית נפרדת (`.venv`).

## 1. פתיחת הפרויקט

1. ב-VS Code: **File → Open Folder** → `Desktop\grocery-price-tracker`
2. פתח טרמינל: **Terminal → New Terminal** (PowerShell)

## 2. מסד נתונים ב-Neon (חינם, בלי כרטיס אשראי)

> למה לא Supabase? בתוכנית החינמית של Supabase אפשר רק שני פרויקטים פעילים, ושני הפרויקטים שלך כבר תפוסים.
> Neon נותן PostgreSQL רגיל בחינם, 0.5 GB לפרויקט. לכן ברירת המחדל היא 6 סניפים לכל רשת (אפשר לשנות ב-`config/settings.yaml`).

1. neon.tech → **Sign up** (אפשר עם חשבון GitHub).
2. **Create project** → שם: `grocery-prices`, גרסת Postgres: 16 או 17, אזור: **AWS Europe Central (Frankfurt)**.
3. בדף הפרויקט: **Connect** → ודא ש-**Connection pooling** מסומן → העתק את ה-connection string.
   הוא נראה בערך כך:
   `postgresql://neondb_owner:XXXX@ep-cool-name-123456-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require`

## 3. התקנה

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

הסקריפט יוצר `.venv`, מתקין את כל הספריות ויוצר קובץ `.env`.
פתח את `.env` והדבק את ה-connection string בשורה `DATABASE_URL=...`.

מעכשיו, בכל טרמינל חדש:

```powershell
.\.venv\Scripts\Activate.ps1
```

(אם PowerShell חוסם הרצת סקריפטים: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`)

## 4. בדיקה שהכול עובד

```powershell
pytest                              # 22 בדיקות אמורות לעבור (3 מדולגות בלי מסד בדיקה)
python -m pricetracker migrate      # יוצר את הטבלאות ב-Neon
python -m pricetracker chains       # רשימת הרשתות
```

## 5. ריצה ראשונה — רשת אחת

```powershell
python -m pricetracker run --chain shufersal
```

מה אמור לקרות: הורדת קובץ הסניפים → בחירת עד 6 סניפים בצפון → הורדת קובץ מחירים וקובץ מבצעים לכל סניף.
בסוף תופיע שורה כמו `run 1: success — 24 loaded, 0 skipped, 0 failed`.

אחר כך רשת שעובדת ב-FTP:

```powershell
python -m pricetracker run --chain rami_levy
```

> אם Windows שואל על חומת אש עבור Python — לאשר (צריך את זה ל-FTP).
> אם רשת נכשלת — תשלח לי את הלוג. אתרי הרשתות משתנים מדי פעם, וזה בדיוק מה שנתקן ביחד.

## 6. כל הרשתות + dbt + אנליטיקה

```powershell
python -m pricetracker daily
```

זה מריץ: איסוף מכל הרשתות → `dbt seed` + `dbt build` (כולל הבדיקות) → זיהוי חריגות ותחזית → ניקוי קבצים ישנים.

> התחזית מתחילה לעבוד אחרי 21 ימים של נתונים. עד אז זה תקין שכתוב "skipping".

## 7. הרצה אוטומטית כל יום

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
```

המשימה רצה כל יום ב-09:00. אם המחשב היה כבוי, היא תרוץ כשהוא נדלק. לוג יומי: `logs\daily-YYYY-MM-DD.log`.

## 8. האתר (Next.js)

1. ב-Neon → **SQL Editor** → הרץ (עם סיסמה ארוכה משלך, 16 תווים ומעלה — Neon דוחה סיסמאות חלשות):
   ```sql
   ALTER ROLE web_reader WITH LOGIN PASSWORD 'סיסמה-חזקה-כאן';
   ```
2. בטרמינל:
   ```powershell
   cd web
   copy .env.example .env.local
   ```
   ב-`.env.local` שים את אותו connection string, אבל במקום `neondb_owner:XXXX` כתוב `web_reader:` והסיסמה החדשה.
3. ```powershell
   npm install
   npm run dev
   ```
   פתח http://localhost:3000

## 9. העלאה ל-GitHub ול-Vercel

```powershell
cd ..
git init
git add .
git commit -m "Israel grocery price tracker"
```

ב-GitHub צור ריפו חדש בשם `grocery-price-tracker` (בלי README), ואז:

```powershell
git remote add origin https://github.com/moatsemkhalifa88-ai/grocery-price-tracker.git
git branch -M main
git push -u origin main
```

ב-Vercel: **Add New → Project** → בחר את הריפו → **Root Directory: `web`** → ב-Environment Variables הוסף
`DATABASE_URL_READONLY` (ה-URI של web_reader) → **Deploy**.

> `.env` לא עולה ל-GitHub (הוא ב-`.gitignore`). לעולם לא להעלות סיסמאות.

## 10. Power BI

הוראות מלאות ב-`powerbi\README.md`: חיבור ל-Neon, קשרים בין הטבלאות (Star Schema), ומדדי DAX מוכנים ב-`powerbi\measures.dax`.

## 11. לפתח בלי לחכות לנתונים (אופציונלי)

```powershell
python scripts\generate_demo_data.py
```

יוצר 45 ימים של נתונים **מומצאים** (ברקודים שמתחילים ב-7299999). לטעון אותם **רק** למסד נתונים נפרד לפיתוח
(למשל פרויקט Neon שני — בחינם אפשר כמה פרויקטים), אף פעם לא למסד שהאתר הציבורי קורא ממנו.

## 12. מה לכתוב בקורות החיים

**Israel Grocery Price Tracker** | Python, PostgreSQL, dbt, Next.js, Power BI
- Built a daily pipeline that ingests price, promotion and store files from 5 Israeli supermarket chains (HTTP + FTPS), with a schema-tolerant XML parser for inconsistent formats and encodings
- Modeled price history as SCD Type 2 in PostgreSQL (stores only changes) and a dbt star schema with data-quality tests
- Computed a Jevons basket price index per chain, robust z-score price anomaly detection and a backtested Holt forecast
- Published a Hebrew RTL dashboard (Next.js, Vercel) and a Power BI report; CI with GitHub Actions

> אחרי שבועיים-שלושה של ריצה, תוסיף מספרים אמיתיים (כמה סניפים, כמה שורות, אחוז החיסכון בנפח).
