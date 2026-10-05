async function searchUsers() {
    const search = document.getElementById('search-users').value;
    const response = await fetch(`/api/users/search?user=${search}`);
    const users = await response.json();

    const usersList = document.getElementById('user-list');
    usersList.textContent = ''; // replaced  with textContent for safer rendering 
    if (users.users.length) {
	users.users.map(user => { //start of compound statement
	    const div = document.createElement('div');
	    div.className = "p-4 bg-gray-700 rounded-md";
	    const p = document.createElement('p');
	    p.className="text-white";
	    p.textContent=user.username;
	    div.appendChild(p);
	    usersList.appendChild(div)
	}
		       )
    }
}

searchUsers();
window.searchUsers = searchUsers;
