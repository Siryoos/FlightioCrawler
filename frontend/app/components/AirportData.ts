export interface Airport {
  icao: string;
  iata: string;
  name: string;
  city: string;
  type: string;
  country?: string;
  passengers?: number;
}

export const IRANIAN_AIRPORTS: Airport[] = [
  { icao: 'OIAA', iata: 'ABD', name: 'فرودگاه بین المللی آبادان', city: 'آبادان', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OISA', iata: '', name: 'فرودگاه آباده', city: 'آباده', type: 'در دست ساخت', country: 'Iran' },
  { icao: 'OICD', iata: '', name: 'فرودگاه آبدانان', city: 'آبدانان', type: 'داخلی', country: 'Iran' },
  { icao: 'OIAG', iata: 'AKW', name: 'فرودگاه آغاجاری', city: 'آغاجاری', type: 'داخلی', country: 'Iran' },
  { icao: 'OIBA', iata: 'AEU', name: 'فرودگاه ابوموسی', city: 'ابوموسی', type: 'داخلی', country: 'Iran' },
  { icao: 'OIHR', iata: 'AJK', name: 'فرودگاه اراک', city: 'اراک', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OITL', iata: 'ADU', name: 'فرودگاه اردبیل', city: 'اردبیل', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OITR', iata: 'OMH', name: 'فرودگاه بین‌المللی شهید باکری ارومیه', city: 'ارومیه', type: 'بین‌المللی', country: 'Iran' },
  { icao: 'OIFM', iata: 'IFN', name: 'فرودگاه بین‌المللی شهید بهشتی اصفهان', city: 'اصفهان', type: 'بین‌المللی', country: 'Iran' },
  { icao: 'OIAW', iata: 'AWZ', name: 'فرودگاه بین‌المللی شهید قاسم سلیمانی', city: 'اهواز', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIZI', iata: 'IHR', name: 'فرودگاه شهدای ایرانشهر', city: 'ایرانشهر', type: 'داخلی', country: 'Iran' },
  { icao: 'OICI', iata: 'IIL', name: 'فرودگاه ایلام', city: 'ایلام', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OINB', iata: 'BBL', name: 'فرودگاه بابلسر', city: 'بابلسر', type: 'داخلی', country: 'Iran' },
  { icao: 'OIMN', iata: 'BJB', name: 'فرودگاه شهدای بجنورد', city: 'بجنورد', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIKM', iata: 'BXR', name: 'فرودگاه بم', city: 'بم', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OITM', iata: 'ACP', name: 'فرودگاه شهید رحمتی', city: 'بناب', type: 'داخلی', country: 'Iran' },
  { icao: 'OIKB', iata: 'BND', name: 'فرودگاه بین‌المللی بندرعباس', city: 'بندرعباس', type: 'بین‌المللی', country: 'Iran' },
  { icao: 'OIKP', iata: 'HDR', name: 'فرودگاه هوادریا', city: 'بندرعباس', type: '', country: 'Iran' },
  { icao: 'OIBL', iata: 'BDH', name: 'فرودگاه بندرلنگه', city: 'بندرلنگه', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIBB', iata: 'BUZ', name: 'فرودگاه بوشهر', city: 'بوشهر', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIAE', iata: '', name: 'فرودگاه بهبهان', city: 'بهبهان', type: 'داخلی', country: 'Iran' },
  { icao: 'OI20', iata: 'IAQ', name: 'فرودگاه بهرگان', city: 'بهرگان،(امام‌حسن)', type: 'داخلی', country: 'Iran' },
  { icao: 'OIMB', iata: 'XBJ', name: 'فرودگاه بیرجند', city: 'بیرجند', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OITP', iata: 'PFQ', name: 'فرودگاه پارس‌آباد مغان', city: 'پارس‌آباد', type: 'داخلی', country: 'Iran' },
  { icao: 'OITH', iata: 'KHA', name: 'فرودگاه خانه', city: 'پیرانشهر', type: 'داخلی', country: 'Iran' },
  { icao: 'OITT', iata: 'TBZ', name: 'فرودگاه بین‌المللی شهید مدنی تبریز', city: 'تبریز', type: 'بین‌المللی', country: 'Iran' },
  { icao: 'OIIE', iata: 'IKA', name: 'فرودگاه بین‌المللی امام خمینی', city: 'تهران', type: 'بین‌المللی', country: 'Iran', passengers: 7429391 },
  { icao: 'OIII', iata: 'THR', name: 'فرودگاه بین‌المللی مهرآباد', city: 'تهران', type: 'بین‌المللی', country: 'Iran', passengers: 12355296 },
  { icao: 'OIIG', iata: '', name: 'فرودگاه قلعه‌مرغی', city: 'تهران', type: '', country: 'Iran' },
  { icao: 'OIZJ', iata: '', name: 'فرودگاه جاسک', city: 'جاسک', type: 'داخلی', country: 'Iran' },
  { icao: 'OIBX', iata: '', name: 'فرودگاه تنب بزرگ', city: 'جزیره تنب بزرگ', type: 'داخلی', country: 'Iran' },
  { icao: 'OIBQ', iata: 'KHK', name: 'فرودگاه خارگ', city: 'جزیره خارگ', type: '', country: 'Iran' },
  { icao: 'OIBS', iata: 'SXI', name: 'فرودگاه جزیره سیری', city: 'جزیره سیری', type: 'داخلی', country: 'Iran' },
  { icao: 'OIBV', iata: 'LVP', name: 'فرودگاه لاوان', city: 'جزیره لاوان', type: 'داخلی', country: 'Iran' },
  { icao: 'OIBJ', iata: 'KNR', name: 'فرودگاه توحید جم', city: 'جم', type: 'اختصاصی', country: 'Iran' },
  { icao: 'OISJ', iata: 'JAR', name: 'فرودگاه بین‌المللی جهرم', city: 'جهرم', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIKJ', iata: 'JYR', name: 'فرودگاه جیرفت', city: 'جیرفت', type: 'داخلی', country: 'Iran' },
  { icao: 'OIZC', iata: 'ZBR', name: 'فرودگاه کنارک', city: 'چابهار', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OISD', iata: '', name: 'فرودگاه داراب', city: 'داراب', type: 'داخلی', country: 'Iran' },
  { icao: 'OIAD', iata: 'DEF', name: 'فرودگاه بین‌المللی دزفول', city: 'دزفول', type: 'بین‌المللی', country: 'Iran' },
  { icao: 'OISF', iata: 'FAZ', name: 'فرودگاه فسا', city: 'فسا', type: 'داخلی', country: 'Iran' },
  { icao: 'OIAH', iata: 'GCH', name: 'فرودگاه شهید امیدبخش گچساران', city: 'گچساران', type: 'داخلی', country: 'Iran' },
  { icao: '', iata: '', name: 'فرودگاه گنبد کاووس', city: 'گنبد کاووس', type: 'داخلی', country: 'Iran' },
  { icao: 'OING', iata: 'GBT', name: 'فرودگاه گرگان', city: 'گرگان', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OINE', iata: 'KLM', name: 'فرودگاه کلاله', city: 'کلاله', type: 'داخلی', country: 'Iran' },
  { icao: 'OIIP', iata: '', name: 'فرودگاه بین‌المللی پیام', city: 'کرج', type: 'بین‌المللی', country: 'Iran' },
  { icao: 'OIKK', iata: 'KER', name: 'فرودگاه بین‌المللی آیت‌الله هاشمی رفسنجانی کرمان', city: 'کرمان', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OICC', iata: 'KSH', name: 'فرودگاه بین‌المللی شهید اشرفی کرمانشاه', city: 'کرمانشاه', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OICK', iata: 'KHD', name: 'فرودگاه بین‌المللی شهدای خرم‌آباد', city: 'خرم‌آباد', type: 'بین المللی', country: 'Iran' },
  { icao: 'OITK', iata: 'KHY', name: 'فرودگاه خوی', city: 'خوی', type: 'داخلی', country: 'Iran' },
  { icao: 'OIBK', iata: 'KIH', name: 'فرودگاه بین‌المللی کیش', city: 'کیش', type: 'بین‌المللی', country: 'Iran' },
  { icao: 'OISR', iata: 'LFM', name: 'فرودگاه بین‌المللی شهدای لامرد', city: 'لامرد', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OISL', iata: 'LRR', name: 'فرودگاه بین‌المللی آیت‌الله آیت‌اللهی لارستان', city: 'لارستان', type: 'بین المللی', country: 'Iran' },
  { icao: 'OIAM', iata: 'MRX', name: 'فرودگاه بندرماهشهر', city: 'ماهشهر', type: 'داخلی', country: 'Iran' },
  { icao: 'OIMM', iata: 'MHD', name: 'فرودگاه بین‌المللی شهید هاشمی‌نژاد مشهد', city: 'مشهد', type: 'بین‌المللی', country: 'Iran', passengers: 7074816 },
  { icao: 'OIAI', iata: '', name: 'فرودگاه مسجد سلیمان', city: 'مسجدسلیمان', type: 'داخلی', country: 'Iran' },
  { icao: 'OINN', iata: 'NSH', name: 'فرودگاه نوشهر', city: 'نوشهر', type: 'داخلی', country: 'Iran' },
  { icao: 'OIIK', iata: 'GZW', name: 'فرودگاه قزوین', city: 'قزوین', type: 'داخلی', country: 'Iran' },
  { icao: 'OIIA', iata: '', name: 'فرودگاه آزادی', city: 'قزوین', type: 'داخلی', country: 'Iran' },
  { icao: 'OIKQ', iata: 'GSM', name: 'فرودگاه بین‌المللی قشم', city: 'قشم', type: 'بین المللی', country: 'Iran' },
  { icao: '', iata: '', name: 'فرودگاه جنوبی قشم', city: 'قشم', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIIQ', iata: '', name: 'فرودگاه بین‌المللی قم', city: 'قم', type: 'در دست احداث', country: 'Iran' },
  { icao: 'OIFK', iata: 'KSN', name: 'فرودگاه کاشان', city: 'کاشان', type: 'داخلی', country: 'Iran' },
  { icao: 'OIKR', iata: 'RJN', name: 'فرودگاه رفسنجان', city: 'رفسنجان', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OINR', iata: 'RZR', name: 'فرودگاه شهدای رامسر', city: 'رامسر', type: 'داخلی', country: 'Iran' },
  { icao: 'OIGG', iata: 'RAS', name: 'فرودگاه بین‌المللی سردار جنگل رشت', city: 'رشت', type: 'بین‌المللی', country: 'Iran' },
  { icao: 'OIMS', iata: 'AFZ', name: 'فرودگاه بین المللی شهدای سبزوار', city: 'سبزوار', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OITS', iata: 'TQZ', name: 'فرودگاه سقز', city: 'سقز', type: 'مرز هوایی', country: 'Iran' },
  { icao: '', iata: '', name: 'فرودگاه فردوس', city: 'فردوس', type: 'در حال احداث', country: 'Iran' },
  { icao: 'OICS', iata: 'SDG', name: 'فرودگاه سنندج', city: 'سنندج', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIMC', iata: 'CKT', name: 'فرودگاه سرخس', city: 'سرخس', type: 'داخلی', country: 'Iran' },
  { icao: 'OIZS', iata: '', name: 'فرودگاه سراوان', city: 'سراوان', type: 'داخلی', country: 'Iran' },
  { icao: 'OINZ', iata: 'SRY', name: 'فرودگاه بین‌المللی دشت ناز ساری', city: 'ساری', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIIS', iata: '', name: 'فرودگاه سمنان', city: 'سمنان', type: 'داخلی', country: 'Iran' },
  { icao: 'OI21', iata: '', name: 'فرودگاه جدید سمنان', city: 'سمنان', type: 'داخلی', country: 'Iran' },
  { icao: 'OIBI', iata: 'YEH', name: 'فرودگاه عسلویه', city: 'عسلویه', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIBP', iata: 'PGU', name: 'فرودگاه بین‌المللی خلیج فارس', city: 'عسلویه', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIFS', iata: 'CQD', name: 'فرودگاه بین‌المللی شهدای شهرکرد', city: 'شهرکرد', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIMJ', iata: '', name: 'فرودگاه شاهرود', city: 'شاهرود', type: 'داخلی', country: 'Iran' },
  { icao: 'OISS', iata: 'SYZ', name: 'فرودگاه بین‌المللی شهید دستغیب شیراز', city: 'شیراز', type: 'بین‌المللی', country: 'Iran' },
  { icao: 'OIKY', iata: 'SYJ', name: 'فرودگاه سیرجان', city: 'سیرجان', type: 'داخلی', country: 'Iran' },
  { icao: 'OIMT', iata: 'TCX', name: 'فرودگاه شهدای طبس', city: 'طبس', type: 'داخلی', country: 'Iran' },
  { icao: 'OIZB', iata: 'ACZ', name: 'فرودگاه زابل', city: 'زابل', type: 'داخلی', country: 'Iran' },
  { icao: 'OIZH', iata: 'ZAH', name: 'فرودگاه بین‌المللی شهدای زاهدان', city: 'زاهدان', type: 'بین‌المللی', country: 'Iran' },
  { icao: 'OITZ', iata: 'JWN', name: 'فرودگاه زنجان', city: 'زنجان', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OISO', iata: '', name: 'فرودگاه زرقان', city: 'زرقان', type: 'آموزشی', country: 'Iran' },
  { icao: 'OIHH', iata: 'HDM', name: 'فرودگاه همدان', city: 'همدان', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OISY', iata: 'YES', name: 'فرودگاه بین المللی شهدای یاسوج', city: 'یاسوج', type: 'داخلی', country: 'Iran' },
  { icao: 'OIYY', iata: 'AZD', name: 'فرودگاه شهید صدوقی یزد', city: 'یزد', type: 'مرز هوایی', country: 'Iran' },
  { icao: 'OIFV', iata: '', name: 'فرودگاه زرین‌شهر', city: 'زرین‌شهر', type: 'داخلی', country: 'Iran' }
];

// Middle East International Airports
export const MIDDLE_EAST_AIRPORTS: Airport[] = [
  // UAE
  { icao: 'OMDB', iata: 'DXB', name: 'فرودگاه بین‌المللی دبی', city: 'Dubai', type: 'بین‌المللی', country: 'UAE', passengers: 92300000 },
  { icao: 'OMAA', iata: 'AUH', name: 'فرودگاه بین‌المللی ابوظبی', city: 'Abu Dhabi', type: 'بین‌المللی', country: 'UAE', passengers: 29400000 },
  { icao: 'OMSJ', iata: 'SHJ', name: 'فرودگاه بین‌المللی شارجه', city: 'Sharjah', type: 'بین‌المللی', country: 'UAE', passengers: 17101725 },
  { icao: 'OMDW', iata: 'DWC', name: 'فرودگاه بین‌المللی آل مکتوم', city: 'Dubai', type: 'بین‌المللی', country: 'UAE' },
  { icao: 'OMRK', iata: 'RKT', name: 'فرودگاه بین‌المللی رأس‌الخیمه', city: 'Ras Al Khaimah', type: 'بین‌المللی', country: 'UAE' },
  
  // Saudi Arabia
  { icao: 'OEJN', iata: 'JED', name: 'فرودگاه بین‌المللی ملک عبدالعزیز (جده)', city: 'Jeddah', type: 'بین‌المللی', country: 'Saudi Arabia', passengers: 49100000 },
  { icao: 'OERK', iata: 'RUH', name: 'فرودگاه بین‌المللی ملک خالد (ریاض)', city: 'Riyadh', type: 'بین‌المللی', country: 'Saudi Arabia', passengers: 37000000 },
  { icao: 'OEDF', iata: 'DMM', name: 'فرودگاه بین‌المللی ملک فهد (دمام)', city: 'Dammam', type: 'بین‌المللی', country: 'Saudi Arabia', passengers: 12000000 },
  { icao: 'OEMA', iata: 'MED', name: 'فرودگاه بین‌المللی شاهزاده محمد بن عبدالعزیز (مدینه)', city: 'Medina', type: 'بین‌المللی', country: 'Saudi Arabia', passengers: 10912802 },
  
  // Qatar
  { icao: 'OTHH', iata: 'DOH', name: 'فرودگاه بین‌المللی حمد (دوحه)', city: 'Doha', type: 'بین‌المللی', country: 'Qatar', passengers: 52700000 },
  
  // Turkey
  { icao: 'LTFM', iata: 'IST', name: 'فرودگاه بین‌المللی استانبول', city: 'Istanbul', type: 'بین‌المللی', country: 'Turkey', passengers: 80430740 },
  { icao: 'LTFJ', iata: 'SAW', name: 'فرودگاه بین‌المللی صبیحه گوکچن (استانبول)', city: 'Istanbul', type: 'بین‌المللی', country: 'Turkey', passengers: 41449044 },
  { icao: 'LTAC', iata: 'ESB', name: 'فرودگاه بین‌المللی اسن‌بوغا (آنکارا)', city: 'Ankara', type: 'بین‌المللی', country: 'Turkey', passengers: 12913753 },
  { icao: 'LTAI', iata: 'AYT', name: 'فرودگاه آنتالیا', city: 'Antalya', type: 'بین‌المللی', country: 'Turkey', passengers: 38133273 },
  { icao: 'LTBS', iata: 'ADB', name: 'فرودگاه عدنان مندرس (ازمیر)', city: 'İzmir', type: 'بین‌المللی', country: 'Turkey', passengers: 11507296 },
  
  // Egypt
  { icao: 'HECA', iata: 'CAI', name: 'فرودگاه بین‌المللی قاهره', city: 'Cairo', type: 'بین‌المللی', country: 'Egypt', passengers: 27700000 },
  { icao: 'HESH', iata: 'SSH', name: 'فرودگاه بین‌المللی شرم‌الشیخ', city: 'Sharm El Sheikh', type: 'بین‌المللی', country: 'Egypt', passengers: 6400000 },
  { icao: 'HEGN', iata: 'HRG', name: 'فرودگاه بین‌المللی غردقه', city: 'Hurghada', type: 'بین‌المللی', country: 'Egypt', passengers: 9500000 },
  { icao: 'HEBA', iata: 'HBE', name: 'فرودگاه برج‌العرب (اسکندریه)', city: 'Alexandria', type: 'بین‌المللی', country: 'Egypt' },
  
  // Iraq
  { icao: 'ORBI', iata: 'BGW', name: 'فرودگاه بین‌المللی بغداد', city: 'Baghdad', type: 'بین‌المللی', country: 'Iraq' },
  { icao: 'ORER', iata: 'EBL', name: 'فرودگاه بین‌المللی اربیل', city: 'Erbil', type: 'بین‌المللی', country: 'Iraq' },
  { icao: 'ORSU', iata: 'ISU', name: 'فرودگاه بین‌المللی سلیمانیه', city: 'Sulaymaniyah', type: 'بین‌المللی', country: 'Iraq' },
  { icao: 'ORMM', iata: 'BSR', name: 'فرودگاه بین‌المللی بصره', city: 'Basra', type: 'بین‌المللی', country: 'Iraq' },
  { icao: 'ORNI', iata: 'NJF', name: 'فرودگاه بین‌المللی نجف', city: 'Najaf', type: 'بین‌المللی', country: 'Iraq' },
  
  // Jordan
  { icao: 'OJAI', iata: 'AMM', name: 'فرودگاه بین‌المللی ملکه علیا (امان)', city: 'Amman', type: 'بین‌المللی', country: 'Jordan', passengers: 8798595 },
  { icao: 'OJAM', iata: 'ADJ', name: 'فرودگاه کشوری امان (مارکا)', city: 'Amman', type: 'داخلی', country: 'Jordan' },
  { icao: 'OJAQ', iata: 'AQJ', name: 'فرودگاه بین‌المللی ملک حسین (عقبه)', city: 'Aqaba', type: 'بین‌المللی', country: 'Jordan' },
  
  // Kuwait
  { icao: 'OKBK', iata: 'KWI', name: 'فرودگاه بین‌المللی کویت', city: 'Kuwait City', type: 'بین‌المللی', country: 'Kuwait', passengers: 15384590 },
  
  // Bahrain
  { icao: 'OBBI', iata: 'BAH', name: 'فرودگاه بین‌المللی بحرین', city: 'Muharraq', type: 'بین‌المللی', country: 'Bahrain', passengers: 9400000 },
  
  // Oman
  { icao: 'OOMS', iata: 'MCT', name: 'فرودگاه بین‌المللی مسقط', city: 'Muscat', type: 'بین‌المللی', country: 'Oman', passengers: 12899829 },
  { icao: 'OOSA', iata: 'SLL', name: 'فرودگاه صلاله', city: 'Salalah', type: 'بین‌المللی', country: 'Oman' },
  
  // Lebanon
  { icao: 'OLBA', iata: 'BEY', name: 'فرودگاه بین‌المللی رفیق حریری بیروت', city: 'Beirut', type: 'بین‌المللی', country: 'Lebanon', passengers: 5620000 },
  
  // Syria
  { icao: 'OSDI', iata: 'DAM', name: 'فرودگاه بین‌المللی دمشق', city: 'Damascus', type: 'بین‌المللی', country: 'Syria' },
  { icao: 'OSLK', iata: 'LTK', name: 'فرودگاه بین‌المللی باسل الاسد (لاذقیه)', city: 'Latakia', type: 'بین‌المللی', country: 'Syria' },
  { icao: 'OSAP', iata: 'ALP', name: 'فرودگاه بین‌المللی حلب', city: 'Aleppo', type: 'بین‌المللی', country: 'Syria' },
  
  // Yemen
  { icao: 'OYSN', iata: 'SAH', name: 'فرودگاه بین‌المللی صنعا', city: 'Sanaa', type: 'بین‌المللی', country: 'Yemen' },
  { icao: 'OYAA', iata: 'ADE', name: 'فرودگاه بین‌المللی عدن', city: 'Aden', type: 'بین‌المللی', country: 'Yemen' },
  { icao: 'OYRN', iata: 'RIY', name: 'فرودگاه بین‌المللی ریان (مکلا)', city: 'Mukalla', type: 'بین‌المللی', country: 'Yemen' },
  
  // Additional previously included airports
  { icao: 'LTBS', iata: 'DLM', name: 'فرودگاه دالامان', city: 'Dalaman', type: 'بین‌المللی', country: 'Turkey', passengers: 5637067 },
  { icao: 'LCLK', iata: 'LCA', name: 'فرودگاه بین‌المللی لارناکا', city: 'Larnaca', type: 'بین‌المللی', country: 'Cyprus', passengers: 8661354 },
  { icao: 'LLBG', iata: 'TLV', name: 'فرودگاه بین‌المللی بن گوریون', city: 'Tel Aviv', type: 'بین‌المللی', country: 'Israel', passengers: 13879490 }
];

// Combined list of all airports
export const ALL_AIRPORTS: Airport[] = [...IRANIAN_AIRPORTS, ...MIDDLE_EAST_AIRPORTS];

// Popular airports for quick access (updated with regional airports)
export const POPULAR_AIRPORTS = [
  // Iran - most popular
  'THR', // تهران - مهرآباد
  'IKA', // تهران - امام خمینی
  'MHD', // مشهد
  'SYZ', // شیراز
  'IFN', // اصفهان
  'TBZ', // تبریز
  'AWZ', // اهواز
  'KIH', // کیش
  'RAS', // رشت
  'KER', // کرمان
  'KSH', // کرمانشاه
  'BND', // بندرعباس
  
  // Middle East - most popular
  'DXB', // Dubai
  'IST', // Istanbul
  'DOH', // Doha
  'JED', // Jeddah
  'RUH', // Riyadh
  'SAW', // Istanbul Sabiha
  'AUH', // Abu Dhabi
  'CAI', // Cairo
  'KWI', // Kuwait
  'MCT', // Muscat
  'BAH', // Bahrain
  'AMM', // Amman
  'AYT', // Antalya
  'ESB', // Ankara
  'BEY', // Beirut
  'TLV', // Tel Aviv
  'BGW', // Baghdad
  'EBL', // Erbil
  'LCA'  // Larnaca
];

export function getAirportByCode(code: string): Airport | undefined {
  return ALL_AIRPORTS.find(airport => 
    airport.iata === code || airport.icao === code
  );
}

export function searchAirports(query: string): Airport[] {
  const searchTerm = query.toLowerCase().trim();
  if (!searchTerm) return ALL_AIRPORTS;
  
  return ALL_AIRPORTS.filter(airport => 
    airport.city.toLowerCase().includes(searchTerm) || 
    airport.name.toLowerCase().includes(searchTerm) ||
    airport.iata.toLowerCase().includes(searchTerm) ||
    airport.icao.toLowerCase().includes(searchTerm) ||
    (airport.country && airport.country.toLowerCase().includes(searchTerm)) ||
    // جستجوی فارسی برای شهرها و کشورها
    (searchTerm === 'دبی' || searchTerm === 'dubai') && airport.city.toLowerCase().includes('dubai') ||
    (searchTerm === 'استانبول' || searchTerm === 'istanbul') && airport.city.toLowerCase().includes('istanbul') ||
    (searchTerm === 'مشهد' || searchTerm === 'mashhad') && airport.city.includes('مشهد') ||
    (searchTerm === 'تهران' || searchTerm === 'tehran') && airport.city.includes('تهران') ||
    (searchTerm === 'شیراز' || searchTerm === 'shiraz') && airport.city.includes('شیراز') ||
    (searchTerm === 'اصفهان' || searchTerm === 'isfahan') && airport.city.includes('اصفهان') ||
    (searchTerm === 'تبریز' || searchTerm === 'tabriz') && airport.city.includes('تبریز') ||
    (searchTerm === 'قاهره' || searchTerm === 'cairo') && airport.city.toLowerCase().includes('cairo') ||
    (searchTerm === 'دوحه' || searchTerm === 'doha') && airport.city.toLowerCase().includes('doha') ||
    (searchTerm === 'ریاض' || searchTerm === 'riyadh') && airport.city.toLowerCase().includes('riyadh') ||
    (searchTerm === 'جده' || searchTerm === 'jeddah') && airport.city.toLowerCase().includes('jeddah') ||
    (searchTerm === 'کویت' || searchTerm === 'kuwait') && airport.city.toLowerCase().includes('kuwait') ||
    (searchTerm === 'بحرین' || searchTerm === 'bahrain') && airport.city.toLowerCase().includes('muharraq') ||
    (searchTerm === 'بیروت' || searchTerm === 'beirut') && airport.city.toLowerCase().includes('beirut') ||
    (searchTerm === 'بغداد' || searchTerm === 'baghdad') && airport.city.toLowerCase().includes('baghdad') ||
    (searchTerm === 'اربیل' || searchTerm === 'erbil') && airport.city.toLowerCase().includes('erbil') ||
    (searchTerm === 'دمشق' || searchTerm === 'damascus') && airport.city.toLowerCase().includes('damascus') ||
    (searchTerm === 'آنکارا' || searchTerm === 'ankara') && airport.city.toLowerCase().includes('ankara') ||
    (searchTerm === 'آنتالیا' || searchTerm === 'antalya') && airport.city.toLowerCase().includes('antalya') ||
    // جستجوی کشورها
    (searchTerm === 'ایران' || searchTerm === 'iran') && airport.country === 'Iran' ||
    (searchTerm === 'امارات' || searchTerm === 'uae') && airport.country === 'UAE' ||
    (searchTerm === 'ترکیه' || searchTerm === 'turkey') && airport.country === 'Turkey' ||
    (searchTerm === 'عربستان' || searchTerm === 'saudi') && airport.country === 'Saudi Arabia' ||
    (searchTerm === 'قطر' || searchTerm === 'qatar') && airport.country === 'Qatar' ||
    (searchTerm === 'مصر' || searchTerm === 'egypt') && airport.country === 'Egypt' ||
    (searchTerm === 'عراق' || searchTerm === 'iraq') && airport.country === 'Iraq' ||
    (searchTerm === 'اردن' || searchTerm === 'jordan') && airport.country === 'Jordan' ||
    (searchTerm === 'کویت' || searchTerm === 'kuwait') && airport.country === 'Kuwait' ||
    (searchTerm === 'بحرین' || searchTerm === 'bahrain') && airport.country === 'Bahrain' ||
    (searchTerm === 'عمان' || searchTerm === 'oman') && airport.country === 'Oman' ||
    (searchTerm === 'لبنان' || searchTerm === 'lebanon') && airport.country === 'Lebanon' ||
    (searchTerm === 'سوریه' || searchTerm === 'syria') && airport.country === 'Syria' ||
    (searchTerm === 'یمن' || searchTerm === 'yemen') && airport.country === 'Yemen' ||
    (searchTerm === 'اسرائیل' || searchTerm === 'israel') && airport.country === 'Israel' ||
    (searchTerm === 'قبرس' || searchTerm === 'cyprus') && airport.country === 'Cyprus'
  );
}

export function getAirportsByCountry(country: string): Airport[] {
  return ALL_AIRPORTS.filter(airport => airport.country === country);
}

export function getTopAirportsByPassengers(limit: number = 10): Airport[] {
  return ALL_AIRPORTS
    .filter(airport => airport.passengers && airport.passengers > 0)
    .sort((a, b) => (b.passengers || 0) - (a.passengers || 0))
    .slice(0, limit);
} 