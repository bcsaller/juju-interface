


var EntityBox = React.createClass({
    getInitialState: function() {
        return {
            q: ""
        };
    },
    setQuery: function(query) {
        this.setState({"q": query});
    },
    render: function() {
        return (
            <div id="entity-box">
            <SearchBox setQuery={this.setQuery}/>
            <EntityCollection query={this.state.q} loggedIn={this.props.loggedIn} kind="interface" url="/api/v1/interfaces"/>
            <EntityCollection query={this.state.q} loggedIn={this.props.loggedIn} kind="layer" url="/api/v1/layers/"/>
            </div>
        );
    }
});

var SearchBox = React.createClass({
    handleQuery: function(e) {
        e.preventDefault();
        var q = React.findDOMNode(this.refs.search).value.trim();
        if (q) {
            this.props.setQuery(e.target.value.trim());
            $(React.findDOMNode(this.refs.searchClear)).show();
        } else {
            $(React.findDOMNode(this.refs.searchClear)).hide();
        }
    },

    clearQuery: function() {
        this.props.setQuery("");
        React.findDOMNode(this.refs.search).value = '';
        $(React.findDOMNode(this.refs.searchClear)).hide();
    },

    componentDidMount: function() {
        $(React.findDOMNode(this.refs.searchClear)).hide();
    },

    render: function() {
        return (
                <div id="search-box">
                    <input autoComplete="off"
                        onKeyUp={this.handleQuery}
                        type="search"
                        ref="search"
                        id="search"
                        placeholder="Search..." />
                        <a href="#" ref="searchClear" id="search-clear" onClick={this.clearQuery}>X</a>
                </div>
        );
    }
})

var EntityCollection = React.createClass({
    getInitialState: function() {
        return {data: []};
    },

    componentDidMount: function() {
        this.queryBackend();

    },

    componentWillReceiveProps: function(props) {
        this.queryBackend({query: props.query});
    },

    queryBackend: function(p) {
        var self = this;
        var query = this.props.query;
        if (p !== undefined) {
            query = p.query;
        }
        var data = {};
        if (query &&  query.length) {
            data['q'] = query;
        }
        $.ajax({
            url: this.props.url,
            data: data,
            dataType: 'json',
            cache: false})
        .done(function(data) {
            if (self.isMounted()) {
                self.setState({data: data});
            }
        })
        .fail(function(xhr, status, err) {
            console.error(self.props.url, status, err.toString());
        });
    },

    render: function() {
        var self = this;
        var entities = this.state.data.map(function(entity, index) {
            return (
                <Entity kind={self.props.kind} repo={entity.repo} key={entity.id} id={entity.id} name={entity.name} summary={entity.summary}/>
            );
        });
        var addNew = "";
        if (this.props.loggedIn === true) {
            var addURL = this.props.kind + '/+/';
            addNew = <a href={addURL}>+</a>;
        }
        return (
            <div className="entityBox" ref={this.props.kind}>
                <h2 className="splash-head">{this.props.kind}: {addNew}</h2>
                <div className="entities">
                   {entities}
                </div>
            </div>
        );
    }
});

var Entity = React.createClass({
    render: function() {
        var detailURL = '/' + this.props.kind + '/' + this.props.id + '/';
        return (
            <div className="entity {this.props.kind}">
                <div className="identity"><a href={detailURL} alt={this.props.id}>{this.props.name}</a></div>
                <div className="repo"><a href={this.props.repo}>Repo</a></div>
                <div className="summary">{this.props.summary}</div>
            </div>
        );
    }
});
