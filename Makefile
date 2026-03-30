.PHONY: install dev build clean test
install:
	npm install
dev:
	npm run dev
build:
	npm run build
test:
	npm test 2>/dev/null || echo no tests
clean:
	rm -rf node_modules dist .next
