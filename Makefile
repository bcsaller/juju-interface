launch:
	docker-compose up
	
populate:
	@echo installing sample data
	curl -d @files/interfaces.json http://localhost:9999/api/v1/interfaces
	curl -d @files/layers http://localhost:9999/api/v1/layers
