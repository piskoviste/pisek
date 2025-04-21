all: out/run out/solve

out/run: run.py
	@mkdir -p out
	cp run.py $@
	chmod +x $@

out/solve: solve.c
	@mkdir -p out
	gcc $^ -o $@

clean:
	rm -rf out
