function responseHandler(response) {
    // Handle the response and return data if there is data; log error if there is error
    if(response.ok) {
        // I know that the returned data will be JSON so it's okay to just give JSON
        return response.json()
    } else {
        throw Error(`${response.url} returned status ${response.status}`);
    }
}

class FetchHTTP {
    // A re-creation of the EasyHTTP API for GET, POST, PUT, and DELETE onto JSON Place Holder dummy API

    constructor(domain) {
        this.domain = domain;
    }    

    async get(path) {
        // If a function is given the async signature, then, without changing any code within the function, any 
        // function call will evaluate to a Promise object that resolves to whatever is returned within the function.
        const url = this.domain + path;
        // The await keyword can be used in front of a Promise object such that:
        //  1.  At runtime, this line will not finish until the Promise object is resolved
        //  2.  The entire "await promise" evaluates to the object that is this Promise object resolves to (or rejects)
        const response = await fetch(url);
        if(response.ok){
            const data = await response.json();
            return data
        } else {
            Promise.reject(Error(`${url} responded with status code ${response.status}`))
        }
        
    }

    async post(path, data) {
        // Given a path and an object to be sent, return a Promise that resolves to the JSON data that is included in 
        // the response from the URL 
        const url = this.domain + path;
        const response = await fetch(url, {
                method: "POST",
                headers: {"Content-type": "application/json"},
                body: JSON.stringify(data)
            }
        );
        const responseData = await response.json();

        return responseData
    }

    // PUT and DELETE are highly similar to that of POST so I am skipping those two to save time
}