Here is an awesome task for you:
You have to create seeder for daily trip assignment properly without flaws. I need this because this is the core concept of waste collection in iwms.
You have to create seeder for this, so that i can fethc the proper data to mobile app frontend and display them as a list of cards or a better ui in operator module frontend:
changes are need for:
operator module in iwms-app
iwms-backend.

So, whats the story?
1. operator logins, 
2. he can see the assigned panachayat on the app header.
3. he can see list of collection points in the panchayat where the trip has been assigned.
4. There is a logic for staff template in backend. you can seed this user in staff template:
username : operator_user
pass: operator123

Use another driver as well.
5. When this staff template is selected for daily tripassignment, the respective operator will dynamically see the trip in his mobile app. 
He will see the list of collection points nearby.
6. He will scan the bin qr in that specific collection point and a screen shows specific details of that colelction points and bin details.
7. Note: a vehicle only collects one type of waste. for eg: vehiclle one collects only wet.
8. so technically,  an operator.driver can be only assigned to collect a single type of waste.
9. how a  colection point is marked as collected?
Answer: There a two bins at a colelction point. one wet and one dry. Since staffs are colelcting one type of waste in a trip, this is waht wll happen daily
 - operator scans the bin qr (eg: wet).
 - he will see the details of that bin and location and other necessary details.
 - he will see a feild to enter waste weight and mark it as collected.
 - the colelction point wll automatically get marked as collected as he collects only one type of waste. although there is a still dry bin not collected, becasuse its a different trip and will be collected by another vehicle.

10. the qr in operator home page is universal. meaning that if operator scans any collection points bin, he marks it as collected.
But there is a catch. if the trip says he is collecting wet, he can only scan wet bins. He can only scan wet bins within the panchayat mentioned in the trip details.
I think there is already a table there to store the waste collected weight with their types, colelction point name, bin, id, and panchayat etc. if missing create one, if there is one, modify it accordingly.

Create necessary seeders in backend with complete analysing the project.

Backend:
test the functions properly.

So when will the trip complete?
When all the collection points are marked as collected, the trip will get completed.
He can see the colelction history and previous summary in the app itself, create the screen accordingly in the app.

UI/UX:
I need amazing attractive easy to understand professional colorful ui for this. Be very experienced designeer in this and complete the task perfectly.

if i missed something, kindly add it as well.


