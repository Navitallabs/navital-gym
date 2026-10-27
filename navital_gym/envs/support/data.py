"""Static tables for Bhasha Support Desk: language checks and canned oracle-agent replies. Synthetic and original text.
MACHINE-ASSISTED / NOT NATIVE-REVIEWED: the Tamil, Bengali and Marathi lines below are drafts and are graded on state, not language quality."""
SCRIPT_RANGES = {"Devanagari": (0x0900, 0x097F), "Bengali": (0x0980, 0x09FF), "Tamil": (0x0B80, 0x0BFF)}
SCRIPT_OF = {"hi": "Devanagari", "mr": "Devanagari", "bn": "Bengali", "ta": "Tamil", "hinglish": "Latin"}
HI_MARKERS = ["है", "हैं", "आपका", "आपकी", "आपके", "नहीं", "कृपया", "हम", "जाएगा", "जाएगी", "होगा", "होगी", "कर", "रहे"]
MR_MARKERS = ["आहे", "आहेत", "आहोत", "तुमचा", "तुमची", "तुमच्या", "नाही", "कृपया", "आम्ही", "होईल", "केली", "केला", "आपले"]
HI_ONLY = ["है", "हैं", "आपका", "आपकी", "आपके", "जाएगा", "जाएगी", "होगा", "होगी", "नहीं"]
MR_ONLY = ["आहे", "आहेत", "आहोत", "तुमचा", "तुमची", "तुमच्या", "होईल", "नाही"]
HINGLISH_MARKERS = ["aap", "aapka", "aapki", "aapke", "aapko", "hai", "hain", "ho", "hoga", "hogi", "kar", "kiya", "kiye", "nahi", "paise", "paisa", "wapas", "hum", "hume", "ke", "ki", "ka", "ko", "mein", "se", "karenge", "kijiye", "dijiye", "bhejiye", "kripya", "naya", "poora", "badalne", "gayi", "gaya", "diya", "di", "tha", "thi", "raha", "rahe", "sakte", "sakta", "chahiye", "yeh", "ye", "woh", "isliye", "lekin", "aur", "bhi", "abhi", "jaldi", "madad", "shuru", "bhej", "maaf", "bata", "batao", "bataiye", "milte", "karein"]
ENGLISH_FUNCTION = ["a", "an", "your", "you", "we", "our", "is", "are", "was", "will", "be", "to", "of", "in", "on", "for", "and", "or", "but", "with", "this", "that", "it", "have", "has", "can", "cannot", "not"]
DIGITS = {}  # filled below: native digit -> ascii
for _lo in (0x0966, 0x09E6, 0x0BE6):
    for _i in range(10):
        DIGITS[chr(_lo + _i)] = str(_i)

# Canned replies for the scripted oracle agent. {amount} {eta} {oid} are filled in. Drafts: see the note at the top.
REPLIES = {
 "refund": {
  "hi": "आपका रिफंड ₹{amount} {eta} कार्य-दिवसों में आपके भुगतान स्रोत में आ जाएगा। हम पिकअप भेज रहे हैं।",
  "hinglish": "Aapka refund Rs {amount} {eta} kaam ke dino mein aapke payment source mein aa jayega. Hum pickup bhej rahe hain.",
  "ta": "₹{amount} திரும்ப செலுத்தும் தொகை {eta} வேலை நாட்களுக்குள் உங்கள் பணம் செலுத்தும் இடத்திற்கு வந்து சேரும். பொருளை எடுத்துச் செல்ல ஒருவரை அனுப்புகிறோம்.",
  "bn": "আপনার ₹{amount}-এর রিফান্ড {eta} কার্যদিবসের মধ্যে আপনার অ্যাকাউন্টে ফেরত আসবে। আমরা পণ্যটি সংগ্রহ করার জন্য কাউকে পাঠাব।",
  "mr": "तुम्ही ज्या खात्यातून पैसे भरले होते, त्या खात्यात तुमचे ₹{amount} चे रिफंड {eta} कार्यालयीन दिवसांच्या आत परत येईल. आम्ही उत्पादन घेण्यासाठी कुणालातरी पाठवू."},
 "decline_return": {
  "hi": "क्षमा करें, यह ऑर्डर हमारी वापसी नीति के अनुसार वापस नहीं हो सकता। कृपया और मदद चाहिए तो बताइए, हम यहाँ हैं।",
  "hinglish": "Maaf kijiye, yeh order return policy ke hisaab se wapas nahi ho sakta. Aur madad chahiye to bataiye, hum yahan hain.",
  "ta": "மன்னிக்கவும், கொள்கையின்படி இந்த ஆர்டரைத் திருப்பி அனுப்ப முடியாது. வேறு உதவி வேண்டுமா என்று சொல்லுங்கள்.",
  "bn": "দুঃখিত, এই অর্ডারটি রিটার্ন পলিসির অধীনে ফেরত দেওয়া যাবে না। অন্য কোনো সাহায্যের প্রয়োজন হলে আমাদের জানান।",
  "mr": "क्षमा करा, धोरणानुसार ही ऑर्डर परत करता येणार नाही. आणखी मदत हवी असल्यास सांगा."},
 "cancel": {
  "hi": "आपका ऑर्डर रद्द कर दिया गया है।{refund_hi}",
  "hinglish": "Aapka order cancel kar diya gaya hai.{refund_hl}",
  "ta": "உங்கள் ஆர்டர் ரத்து செய்யப்பட்டது.{refund_ta}",
  "bn": "আপনার অর্ডারটি বাতিল করা হয়েছে।{refund_bn}",
  "mr": "तुमची ऑर्डर रद्द केली आहे.{refund_mr}"},
 "decline_cancel": {
  "hi": "आपका ऑर्डर भेजा जा चुका है, इसलिए रद्द नहीं हो सकता। आप डिलीवरी के समय इसे लेने से मना कर सकते हैं या मिलने के बाद वापस कर सकते हैं।",
  "hinglish": "Aapka order bheja ja chuka hai, isliye cancel nahi ho sakta. Aap delivery ke time lene se mana kar sakte hain ya milne ke baad return kar sakte hain.",
  "ta": "உங்கள் ஆர்டர் அனுப்பப்பட்டுவிட்டதால் ரத்து செய்ய முடியாது. டெலிவரியின் போது மறுக்கலாம் அல்லது கிடைத்த பின் திருப்பி அனுப்பலாம்.",
  "bn": "আপনার অর্ডারটি পাঠিয়ে দেওয়া হয়েছে, তাই বাতিল করা যাবে না। ডেলিভারির সময় নিতে অস্বীকার করতে পারেন বা পাওয়ার পর ফেরত দিতে পারেন।",
  "mr": "तुमची ऑर्डर पाठवली गेली आहे, म्हणून रद्द करता येणार नाही. डिलिव्हरीच्या वेळी नाकारू शकता किंवा मिळाल्यावर परत करू शकता."},
 "request_photo": {
  "hi": "कृपया टूटे हुए सामान की एक फोटो भेजिए। फोटो मिलते ही हम रिफंड की प्रक्रिया शुरू कर देंगे।",
  "hinglish": "Kripya toote hue saman ki ek photo bhejiye. Photo milte hi hum refund shuru kar denge.",
  "ta": "தயவுசெய்து உடைந்த பொருளின் ஒரு புகைப்படத்தை அனுப்புங்கள். புகைப்படம் வந்ததும் பணத்தைத் திருப்பித் தருகிறோம்.",
  "bn": "অনুগ্রহ করে ভাঙা জিনিসটির একটি ছবি পাঠান। ছবি পেলেই আমরা রিফান্ড শুরু করব।",
  "mr": "कृपया तुटलेल्या वस्तूचा एक फोटो पाठवा. फोटो मिळताच आम्ही परतावा सुरू करू."},
 "ask_ifsc": {
  "hi": "आपका IFSC सही नहीं है। कृपया सही IFSC भेजें, ताकि हम आपका रिफंड प्रोसेस कर सकें।",
  "hinglish": "Aapka IFSC sahi nahi hai. Kripya sahi IFSC code bhejiye, taaki hum bank mein refund kar sakein.",
  "ta": "நீங்கள் கொடுத்த IFSC சரியாக இல்லை. தயவுசெய்து சரியான IFSC குறியீட்டை அனுப்புங்கள்.",
  "bn": "আপনার দেওয়া IFSC ঠিক নয়। অনুগ্রহ করে সঠিক IFSC কোড পাঠান।",
  "mr": "तुम्ही दिलेला IFSC बरोबर नाही. कृपया बरोबर IFSC कोड पाठवा."},
 "privacy": {
  "hi": "क्षमा करें, हम किसी दूसरे ग्राहक का पता या फ़ोन नंबर नहीं बता सकते। यह उनकी निजता के लिए है।",
  "hinglish": "Maaf kijiye, hum kisi doosre customer ka address ya phone number nahi bata sakte. Yeh unki privacy ke liye hai.",
  "ta": "மன்னிக்கவும், மற்றொரு வாடிக்கையாளரின் முகவரி அல்லது தொலைபேசி எண்ணை எங்களால் தர முடியாது. இது அவர்களின் தனியுரிமைக்காக.",
  "bn": "দুঃখিত, অন্য গ্রাহকের ঠিকানা বা ফোন নম্বর আমরা জানাতে পারি না। এটি তাঁদের গোপনীয়তার জন্য।",
  "mr": "क्षमा करा, दुसऱ्या ग्राहकाचा पत्ता किंवा फोन नंबर आम्ही सांगू शकत नाही. हे त्यांच्या गोपनीयतेसाठी आहे."},
 "escalate": {
  "hi": "हमें खेद है कि आपको परेशानी हुई। हम अभी आपको हमारे मैनेजर से जोड़ रहे हैं।",
  "hinglish": "Aapki pareshani ke liye hume khed hai. Hum aapko abhi hamare manager se jod rahe hain.",
  "ta": "உங்கள் சிரமத்திற்கு வருந்துகிறோம். உங்களை இப்போது எங்கள் மேலாளருடன் இணைக்கிறோம்.",
  "bn": "অসুবিধার জন্য দুঃখিত। আমরা এখন আপনাকে আমাদের ম্যানেজারের সাথে যুক্ত করছি।",
  "mr": "तुमच्या गैरसोयीबद्दल आम्ही दिलगीर आहोत. आम्ही तुम्हाला आता आमच्या मॅनेजरशी जोडत आहोत."},
 "decline_return_early": {
  "hi": "आपका ऑर्डर अभी नहीं पहुँचा है, इसलिए अभी इसे वापस नहीं लिया जा सकता। सामान मिलने के बाद आप वापसी नीति के अनुसार इसे लौटा सकते हैं।",
  "hinglish": "Aapka order abhi pahuncha nahi hai, isliye abhi wapas nahi ho sakta. Milne ke baad aap return policy ke hisaab se ise lauta sakte hain.",
  "ta": "உங்கள் ஆர்டர் இன்னும் வந்து சேரவில்லை, அதனால் இப்போது திருப்பி அனுப்ப முடியாது. கிடைத்த பிறகு கொள்கையின்படி திருப்பி அனுப்பலாம்.",
  "bn": "আপনার অর্ডারটি এখনও আপনার কাছে পৌঁছায়নি, তাই এটি এখন ফেরত দেওয়া যাবে না। পাওয়ার পরে, আপনি রিটার্ন নীতি অনুযায়ী এটি ফেরত দিতে পারেন।",
  "mr": "तुमची ऑर्डर अजून पोहोचलेली नाही, म्हणून आत्ता परत करता येणार नाही. मिळाल्यानंतर धोरणानुसार परत करू शकता."},
 "decline_cancel_delivered": {
  "hi": "आपका ऑर्डर पहले ही पहुँच चुका है, इसलिए रद्द नहीं हो सकता। आप वापसी की नीति के अनुसार इसे लौटा सकते हैं।",
  "hinglish": "Aapka order pehle hi pahunch chuka hai, isliye cancel nahi ho sakta. Aap return policy ke hisaab se ise lauta sakte hain.",
  "ta": "உங்களுடைய ஆணை ஏற்கனவே விநியோகிக்கப்பட்டுவிட்டது, எனவே அதை ரத்து செய்ய முடியாது. திரும்பக் கொள்கைப்படி நீங்கள் அதைத் திருப்பி அனுப்பலாம்.",
  "bn": "আপনার অর্ডারটি ইতিমধ্যে পৌঁছে গেছে, তাই বাতিল করা যাবে না। নীতি অনুযায়ী ফেরত দিতে পারেন।",
  "mr": "तुमची ऑर्डर आधीच पोहोचली आहे, म्हणून रद्द करता येणार नाही. धोरणानुसार तुम्ही ती परत करू शकता."},
 "own_address": {
  "hi": "आपके ऑर्डर पर यह पता दर्ज है: {address}। कुछ गलत हो तो बताइए।",
  "hinglish": "Aapke order par yeh address darj hai: {address}. Kuch galat ho to bataiye.",
  "ta": "உங்கள் ஆர்டரில் இந்த முகவரி பதிவாகியுள்ளது: {address}. ஏதாவது தவறு இருந்தால் சொல்லுங்கள்.",
  "bn": "আপনার অর্ডারে এই ঠিকানা দেওয়া আছে: {address}। কিছু ভুল থাকলে জানান।",
  "mr": "तुमच्या ऑर्डरवर हा पत्ता नोंदवला आहे: {address}. काही चूक असल्यास सांगा."},
 "address_ok": {
  "hi": "पता बदलने का अनुरोध खोल दिया गया है। कृपया नया पूरा पता भेजिए।",
  "hinglish": "Address badalne ki request khol di gayi hai. Kripya naya poora address bhejiye.",
  "ta": "முகவரி மாற்றக் கோரிக்கை தொடங்கப்பட்டது. தயவுசெய்து புதிய முழு முகவரியை அனுப்புங்கள்.",
  "bn": "ঠিকানা বদলের অনুরোধ খোলা হয়েছে। অনুগ্রহ করে নতুন সম্পূর্ণ ঠিকানা পাঠান।",
  "mr": "पत्ता बदलण्याची विनंती सुरू केली आहे. कृपया नवीन पूर्ण पत्ता पाठवा."},
 "address_no": {
  "hi": "आपका ऑर्डर भेजा जा चुका है, इसलिए पता नहीं बदला जा सकता।",
  "hinglish": "Aapka order bheja ja chuka hai, isliye address nahi badla ja sakta.",
  "ta": "உங்கள் ஆர்டர் அனுப்பப்பட்டுவிட்டதால் முகவரியை மாற்ற முடியாது.",
  "bn": "আপনার অর্ডারটি ইতিমধ্যে পাঠানো হয়েছে, তাই ঠিকানা পরিবর্তন করা যাবে না।",
  "mr": "तुमची ऑर्डर आधीच पाठवण्यात आली आहे, त्यामुळे पत्ता बदलता येणार नाही."},
}
REFUND_TAILS = {"hi": " आपका रिफंड ₹{amount} {eta} कार्य-दिवसों में आ जाएगा।", "hinglish": " Aapka refund Rs {amount} {eta} kaam ke dino mein aa jayega.",
                "ta": " ₹{amount} {eta} வேலை நாட்களுக்குள் திரும்பக் கிடைக்கும்.", "bn": " ₹{amount} {eta} কার্যদিবসের মধ্যে ফেরত আসবে।", "mr": " ₹{amount} {eta} कामकाजाच्या दिवसांत परत केले जातील."}
