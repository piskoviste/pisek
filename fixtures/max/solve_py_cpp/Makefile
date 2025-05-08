all: target/run target/solve

target/run: run.py
	@mkdir -p target
	cp run.py $@
	chmod +x $@

target/solve: solve.c
	@mkdir -p target
	gcc $^ -o $@

clean:
	rm -rf target
