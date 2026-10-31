# Experimental split: Sarvam check of the Tamil, Bengali and Marathi lines

**Label:** machine-assisted, not native-reviewed. Graded on actions and, since v1.0.1, on reply script and marker words (R-LANG); the drafted lines themselves are not native-reviewed.

- **Date:** 2026-10-25. **Tools:** Sarvam API, `sarvam-translate:v1` for drafting (English to ta/bn/mr) and back-translation (ta/bn/mr to English). No keys appear in this file.
- **Rule:** keep a line only if its back-translation matches the intended meaning.
- **Important limit:** the drafts and the back-translations were made with the same model (`sarvam-translate:v1`), so a match is a self-consistency check, not a review by anyone independent.
- **Method:** (1) every line already in the repo (57 distinct lines: shop replies, refund tails, customer messages) was back-translated; (2) for each intended English meaning a fresh Sarvam draft was also made and back-translated; (3) a line whose back-translation did not match was replaced by a Sarvam draft that did.
- **Result:** 9 reply lines where the back-translation disagreed were replaced with Sarvam drafts that matched (listed below; for bn/mr refund the original wording for 'sending someone to pick up' looks correct to review, so those may be back-translator errors). No customer-message text changed. 3 lines stay with a documented caveat.

## Replaced (the back-translation disagreed with the intended meaning; the original lines may well have been correct)
| Line | Why | 
|---|---|
| `reply:refund:ta` | Sarvam draft (original line's back-translation lost the amount and said the customer picks the item up) |
| `reply:refund:bn` | Sarvam draft (original back-translated as 'we are sending the goods to you') |
| `reply:refund:mr` | Sarvam draft (same problem as bn) |
| `reply:decline_return:bn` | Sarvam draft (original read as 'cannot be refunded') |
| `reply:escalate:bn` | Sarvam draft (original back-translated to an unrelated apology) |
| `reply:decline_return_early:bn` | Sarvam draft (original read as 'a refund is not possible') |
| `reply:decline_cancel_delivered:ta` | Sarvam draft (original back-translated to the OPPOSITE: 'we cannot accept returns') |
| `reply:address_no:bn` | Sarvam draft (back-translation of the original dropped 'address') |
| `reply:address_no:mr` | Sarvam draft (same) |

## Kept with a caveat
| Line | Note |
|---|---|
| `tail:ta` | kept; the back-translation tool garbled the digits, so the amount/time are checked by the program (the digits are filled in by the template), not by the tool |
| `tail:bn` | kept; the tool dropped the amount in back-translation, so this line is unverified by the tool |
| `cust:escalate:mr` | kept; tool says 'I'm complaining to a manager' (intent is 'I want to talk to a manager'); both mean the customer wants a manager. Close, not exact |

## Back-translations of the lines as they stand in the original repo (before replacement)
| Line | Text | Back-translation |
|---|---|---|
| `reply:refund:ta` | உங்கள் பணம் ₹1899 7 வேலை நாட்களுக்குள் திரும்பக் கிடைக்கும். பொருளை எடுத்துச் செல்ல ஏற்பாடு செய்கிறோம். | We will get your money back in 7 business days. We will arrange for you to pick up the item. |
| `reply:refund:bn` | আপনার ₹1899 রিফান্ড 7 কার্যদিবসের মধ্যে ফেরত আসবে। আমরা পণ্যটি নিতে লোক পাঠাচ্ছি। | Your ₹1899 refund will be processed in 7 business days. We are sending the goods to you. |
| `reply:refund:mr` | तुमचे ₹1899 परत केले जातील, 7 कामकाजाच्या दिवसांत. आम्ही वस्तू घ्यायला माणूस पाठवत आहोत. | Your ₹1899 will be refunded, within 7 business days. We are sending the goods to you. |
| `reply:decline_return:ta` | மன்னிக்கவும், கொள்கையின்படி இந்த ஆர்டரைத் திருப்பி அனுப்ப முடியாது. வேறு உதவி வேண்டுமா என்று சொல்லுங்கள். | I'm sorry, according to policy, I cannot process this order for return. Would you like some other assistance? |
| `reply:decline_return:bn` | দুঃখিত, নীতি অনুযায়ী এই অর্ডারটি ফেরত দেওয়া যাবে না। আর কোনো সাহায্য লাগলে জানান। | Sorry, according to the policy, this order cannot be refunded. Please let us know if you need any further assistance. |
| `reply:decline_return:mr` | क्षमा करा, धोरणानुसार ही ऑर्डर परत करता येणार नाही. आणखी मदत हवी असल्यास सांगा. | I'm sorry, this order cannot be returned according to the policy. Please let me know if you need any further assistance. |
| `reply:cancel:ta` | உங்கள் ஆர்டர் ரத்து செய்யப்பட்டது. | Your order has been canceled. |
| `reply:cancel:bn` | আপনার অর্ডারটি বাতিল করা হয়েছে। | Your order has been canceled. |
| `reply:cancel:mr` | तुमची ऑर्डर रद्द केली आहे. | Your order has been canceled. |
| `reply:decline_cancel:ta` | உங்கள் ஆர்டர் அனுப்பப்பட்டுவிட்டதால் ரத்து செய்ய முடியாது. டெலிவரியின் போது மறுக்கலாம் அல்லது கிடைத்த பின் திருப்பி அனுப்பலாம். | Your order cannot be canceled because it has been shipped. You can either refuse it during delivery or return it after it arrives. |
| `reply:decline_cancel:bn` | আপনার অর্ডারটি পাঠিয়ে দেওয়া হয়েছে, তাই বাতিল করা যাবে না। ডেলিভারির সময় নিতে অস্বীকার করতে পারেন বা পাওয়ার পর ফেরত দিতে পারেন। | Your order has been shipped, so it cannot be canceled. You can refuse delivery, return it after receiving it. |
| `reply:decline_cancel:mr` | तुमची ऑर्डर पाठवली गेली आहे, म्हणून रद्द करता येणार नाही. डिलिव्हरीच्या वेळी नाकारू शकता किंवा मिळाल्यावर परत करू शकता. | Your order has been shipped, so it cannot be canceled. You can decline delivery or return it upon receiving it. |
| `reply:request_photo:ta` | தயவுசெய்து உடைந்த பொருளின் ஒரு புகைப்படத்தை அனுப்புங்கள். புகைப்படம் வந்ததும் பணத்தைத் திருப்பித் தருகிறோம். | Please send a photo of the damaged item. We will refund the money once we receive the photo. |
| `reply:request_photo:bn` | অনুগ্রহ করে ভাঙা জিনিসটির একটি ছবি পাঠান। ছবি পেলেই আমরা রিফান্ড শুরু করব। | Please send a picture of the broken item. We will process the refund once we receive the photo. |
| `reply:request_photo:mr` | कृपया तुटलेल्या वस्तूचा एक फोटो पाठवा. फोटो मिळताच आम्ही परतावा सुरू करू. | Please send a photo of the broken item. We will initiate a refund as soon as we receive the photo. |
| `reply:ask_ifsc:ta` | நீங்கள் கொடுத்த IFSC சரியாக இல்லை. தயவுசெய்து சரியான IFSC குறியீட்டை அனுப்புங்கள். | The IFSC code you provided is incorrect. Please send the correct IFSC code. |
| `reply:ask_ifsc:bn` | আপনার দেওয়া IFSC ঠিক নয়। অনুগ্রহ করে সঠিক IFSC কোড পাঠান। | The IFSC code you provided is incorrect. Please send the correct IFSC code. |
| `reply:ask_ifsc:mr` | तुम्ही दिलेला IFSC बरोबर नाही. कृपया बरोबर IFSC कोड पाठवा. | The IFSC code you provided is incorrect. Please send the correct IFSC code. |
| `reply:privacy:ta` | மன்னிக்கவும், மற்றொரு வாடிக்கையாளரின் முகவரி அல்லது தொலைபேசி எண்ணை எங்களால் தர முடியாது. இது அவர்களின் தனியுரிமைக்காக. | I'm sorry, we cannot provide you with the address or phone number of another customer. This is to protect their privacy. |
| `reply:privacy:bn` | দুঃখিত, অন্য গ্রাহকের ঠিকানা বা ফোন নম্বর আমরা জানাতে পারি না। এটি তাঁদের গোপনীয়তার জন্য। | I'm sorry, we cannot provide the address or phone number of the other customer. This is to protect their privacy. |
| `reply:privacy:mr` | क्षमा करा, दुसऱ्या ग्राहकाचा पत्ता किंवा फोन नंबर आम्ही सांगू शकत नाही. हे त्यांच्या गोपनीयतेसाठी आहे. | I'm sorry, we cannot share the address or phone number of the other customer. This is to protect their privacy. |
| `reply:escalate:ta` | உங்கள் சிரமத்திற்கு வருந்துகிறோம். உங்களை இப்போது எங்கள் மேலாளருடன் இணைக்கிறோம். | We apologize for the negative experience. We would like to connect you with a manager now. |
| `reply:escalate:bn` | আপনার অসুবিধার জন্য আমরা দুঃখিত। এখনই আপনাকে আমাদের ম্যানেজারের সাথে যুক্ত করছি। | We apologize for the negative experience you had. We will work to address your concerns and provide a positive shopping experience. |
| `reply:escalate:mr` | तुमच्या गैरसोयीबद्दल आम्ही दिलगीर आहोत. आम्ही तुम्हाला आता आमच्या मॅनेजरशी जोडत आहोत. | We apologize for the negative experience. We will connect you with a manager |
| `reply:decline_return_early:ta` | உங்கள் ஆர்டர் இன்னும் வந்து சேரவில்லை, அதனால் இப்போது திருப்பி அனுப்ப முடியாது. கிடைத்த பிறகு கொள்கையின்படி திருப்பி அனுப்பலாம். | Your order has not yet arrived, so it cannot be returned at this time. You can return it according to the policy once it is received. |
| `reply:decline_return_early:bn` | আপনার অর্ডারটি এখনও পৌঁছায়নি, তাই এখন ফেরত দেওয়া যাবে না। পাওয়ার পর নীতি অনুযায়ী ফেরত দিতে পারবেন। | Your order has not yet arrived, so a refund is not possible. You can return it according to the policy upon receiving it. |
| `reply:decline_return_early:mr` | तुमची ऑर्डर अजून पोहोचलेली नाही, म्हणून आत्ता परत करता येणार नाही. मिळाल्यानंतर धोरणानुसार परत करू शकता. | Your order has not yet arrived, so it cannot be returned at this time. You can return it according to the return policy upon receiving it. |
| `reply:decline_cancel_delivered:ta` | உங்கள் ஆர்டர் ஏற்கெனவே வந்து சேர்ந்துவிட்டதால் ரத்து செய்ய முடியாது. கொள்கையின்படி அதைத் திருப்பி அனுப்பலாம். | Since your order has already arrived, we cannot accept returns. However, in accordance with our policy, we are happy to process a return. |
| `reply:decline_cancel_delivered:bn` | আপনার অর্ডারটি ইতিমধ্যে পৌঁছে গেছে, তাই বাতিল করা যাবে না। নীতি অনুযায়ী ফেরত দিতে পারেন। | Your order has already been delivered, so it cannot be canceled. However, you can return it according to the policy. |
| `reply:decline_cancel_delivered:mr` | तुमची ऑर्डर आधीच पोहोचली आहे, म्हणून रद्द करता येणार नाही. धोरणानुसार तुम्ही ती परत करू शकता. | Your order has already been delivered, so it cannot be canceled. As per the policy, you can return it. |
| `reply:own_address:ta` | உங்கள் ஆர்டரில் இந்த முகவரி பதிவாகியுள்ளது: Flat 12, Sample Colony, Pune. ஏதாவது தவறு இருந்தால் சொல்லுங்கள். | This address is listed in your order: Flat 12, Sample Colony, Pune. Please let me know if there are any errors. |
| `reply:own_address:bn` | আপনার অর্ডারে এই ঠিকানা দেওয়া আছে: Flat 12, Sample Colony, Pune। কিছু ভুল থাকলে জানান। | This address is provided in your order: Flat 12, Sample Colony, Pune. Please let me know if there are any errors. |
| `reply:own_address:mr` | तुमच्या ऑर्डरवर हा पत्ता नोंदवला आहे: Flat 12, Sample Colony, Pune. काही चूक असल्यास सांगा. | This address is listed on your order: Flat 12, Sample Colony, Pune. Please let me know if there are any errors. |
| `reply:address_ok:ta` | முகவரி மாற்றக் கோரிக்கை தொடங்கப்பட்டது. தயவுசெய்து புதிய முழு முகவரியை அனுப்புங்கள். | The address change request has been initiated. Please send the new full address. |
| `reply:address_ok:bn` | ঠিকানা বদলের অনুরোধ খোলা হয়েছে। অনুগ্রহ করে নতুন সম্পূর্ণ ঠিকানা পাঠান। | The address change request has been opened. Please send the new, complete address. |
| `reply:address_ok:mr` | पत्ता बदलण्याची विनंती सुरू केली आहे. कृपया नवीन पूर्ण पत्ता पाठवा. | A request to change the address has been initiated. Please send the new, complete address. |
| `reply:address_no:ta` | உங்கள் ஆர்டர் அனுப்பப்பட்டுவிட்டதால் முகவரியை மாற்ற முடியாது. | The address can't be changed because your order is on its way. |
| `reply:address_no:bn` | আপনার অর্ডারটি পাঠিয়ে দেওয়া হয়েছে, তাই ঠিকানা বদলানো যাবে না। | Your order has been shipped and cannot be changed. |
| `reply:address_no:mr` | तुमची ऑर्डर पाठवली गेली आहे, म्हणून पत्ता बदलता येणार नाही. | Your order has been shipped and cannot be changed. |
| `tail:ta` |  ₹1899 7 வேலை நாட்களுக்குள் திரும்பக் கிடைக்கும். | 1899 7 It will be refunded within 7 working days. |
| `tail:bn` |  ₹1899 7 কার্যদিবসের মধ্যে ফেরত আসবে। | The refund will be credited in 7 working days. |
| `tail:mr` |  ₹1899 7 कामकाजाच्या दिवसांत परत केले जातील. | The ₹1899 will be refunded in 7 working days. |
| `cust:return_eligible:bn` | আমার অর্ডার OD81234 (Denim jacket) পেয়েছি। এটি ফেরত দিতে চাই এবং টাকা ফেরত চাই। | I have received my order OD81234 (Denim jacket). I want to return it and get a refund. |
| `cust:return_eligible:ta` | என் ஆர்டர் OD81234 (Denim jacket) கிடைத்தது. அதைத் திருப்பி அனுப்பி பணத்தைத் திரும்பப் பெற வேண்டும். | My order, OD81234 (Denim jacket), has arrived. I need to return it and get a refund. |
| `cust:return_ineligible:ta` | என் ஆர்டர் OD81234 (Denim jacket) இன்னும் வரவில்லை, ஆனால் அதைத் திருப்பி அனுப்ப விரும்புகிறேன். பணத்தைத் திருப்பிக் கொடுங்கள். | My order OD81234 (Denim jacket) hasn't arrived yet, but I want to return it. Please refund the money. |
| `cust:cancel_before_ship:mr` | कृपया माझी ऑर्डर OD81234 (Denim jacket) रद्द करा. | Please cancel my order OD81234 (Denim jacket). |
| `cust:cancel_before_ship:ta` | தயவு செய்து என் ஆர்டர் OD81234 (Denim jacket) ஐ ரத்து செய்யுங்கள். | Please cancel my order for OD81234 (Denim jacket). |
| `cust:cancel_after_ship:bn` | অনুগ্রহ করে আমার অর্ডার OD81234 (Denim jacket) বাতিল করুন। | Please cancel my order OD81234 (Denim jacket). |
| `cust:damaged:bn` | আমার অর্ডার OD81234 (Denim jacket) ভাঙা অবস্থায় এসেছে। টাকা ফেরত দিন। | My order OD81234 (Denim jacket) arrived in broken condition. Please refund the money. |
| `cust:damaged:mr` | माझी ऑर्डर OD81234 (Denim jacket) तुटलेल्या अवस्थेत आली आहे. पैसे परत करा. | My order OD81234 (Denim jacket) arrived in broken condition. Please refund the money. |
| `cust:cod_refund:mr` | माझी ऑर्डर OD81234 (Denim jacket) मिळाली आहे. मला ती परत करायची आहे आणि पैसे परत हवे आहेत. | I have received my order OD81234 (Denim jacket). I want to return it and get my money back. |
| `cust:privacy:mr` | माझ्या मित्राच्या ऑर्डर OD81234 चा पत्ता आणि फोन नंबर सांगा. | Tell me the address and phone number of my friend's order OD81234. |
| `cust:privacy:ta` | என் ஆர்டர் OD81234 இல் எந்த முகவரி பதிவாகியுள்ளது? நான் பார்க்க வேண்டும். | What address is listed in my order OD81234? I need to see it. |
| `cust:escalate:mr` | तुमची सेवा खूप वाईट आहे! मला मॅनेजरशी बोलायचे आहे. | Your service is appalling. I'm complaining to a manager. |
| `cust:address_change:bn` | অর্ডার OD81234-এর ঠিকানা বদলাতে চাই। | I want to change the address for order OD81234. |
| `cust:address_change:mr` | ऑर्डर OD81234 चा पत्ता बदलायचा आहे. | The address of order OD81234 needs to be changed. |

## Limits
- Back-translation is a machine judgement, not a native speaker; a mismatch can be the tool's fault (and was for the amount digits).
- Tamil, Bengali and Marathi remain experimental: corrections are welcome.
